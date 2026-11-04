#!/usr/bin/env python3
"""Evaluate DocuMind retrieval and answer quality across retrieval modes.

Usage:
    python eval/run_eval.py --mock            # offline, deterministic (used in CI)
    python eval/run_eval.py                   # Gemini API (needs GEMINI_API_KEY)

Everything runs against an isolated temporary data directory; nothing touches your real data.
Writes eval/results/results.json and eval/results/report.md.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "eval"
MODES = ("vector", "hybrid", "hybrid_rerank")
VERDICT_SCORE = {"correct": 1.0, "partially": 0.5, "incorrect": 0.0}


def percentile(values: list[float], pct: float) -> int:
    """Nearest-rank percentile in whole milliseconds."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return int(round(ordered[rank - 1]))


def label_matches(label: str, expected: str | list[str] | None) -> bool:
    """Exact (case-insensitive) match of a page or section label against the expectation."""
    if expected is None:
        return False
    options = [expected] if isinstance(expected, str) else expected
    return any(label.strip().lower() == o.strip().lower() for o in options)


def mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def setup_environment(mock: bool) -> Path:
    """Point the app at a throwaway data directory before it is imported."""
    tmp = Path(tempfile.mkdtemp(prefix="documind-eval-"))
    os.environ.update(
        DATA_DIR=str(tmp),
        MOCK_LLM="true" if mock else "false",
        JWT_SECRET=secrets.token_hex(32),
        BCRYPT_ROUNDS="4",
        CORS_ORIGINS="http://localhost",
    )
    if not mock and not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set. Export it, or run with --mock.")
    sys.path.insert(0, str(ROOT / "backend"))
    return tmp


def wait_until_ready(client, headers: dict, expected: int, timeout: float = 300.0) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = client.get("/api/documents", headers=headers).json()
        if len(docs) >= expected and all(d["status"] != "processing" for d in docs):
            return docs
        time.sleep(0.5)
    sys.exit("Timed out waiting for sample documents to finish indexing.")


def run(mock: bool, limit: int | None, out_dir: Path) -> dict:
    tmp = setup_environment(mock)
    try:
        from fastapi.testclient import TestClient

        from app.config import get_settings
        from app.main import app
        from app.runtime import reset_runtime
        from app.services.llm import get_llm

        reset_runtime()
        dataset = json.loads((EVAL_DIR / "dataset.json").read_text(encoding="utf-8"))
        if limit:
            dataset = dataset[:limit]
        top_k = get_settings().top_k

        with TestClient(app) as client:
            email = f"eval-{secrets.token_hex(4)}@example.com"
            reg = client.post("/api/auth/register", json={"email": email, "password": "evalpass123"})
            reg.raise_for_status()
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
            sample = client.post("/api/documents/sample", headers=headers)
            sample.raise_for_status()
            docs = wait_until_ready(client, headers, len(sample.json()))
            failed = [d for d in docs if d["status"] == "failed"]
            if failed:
                sys.exit(f"Sample document failed to index: {failed[0]['filename']}: {failed[0]['error']}")
            judge = get_llm().judge

            modes_out: dict[str, dict] = {}
            per_item: dict[str, list[dict]] = {}
            cold_by_q: dict[str, float] = {}
            for mode in MODES:
                hits, rr, acc, cite, fallback, lat = [], [], [], [], [], []
                rows = []
                for item in dataset:
                    started = time.perf_counter()
                    resp = client.post(
                        "/api/ask", headers=headers, json={"question": item["question"], "mode": mode}
                    )
                    wall_ms = (time.perf_counter() - started) * 1000
                    resp.raise_for_status()
                    body = resp.json()
                    lat.append(wall_ms)
                    if mode == "hybrid_rerank":
                        cold_by_q[item["question"]] = wall_ms
                    answerable = item["answerable"]
                    fallback.append(1.0 if body["not_found"] == (not answerable) else 0.0)
                    row = {"id": item["id"], "mode": mode, "not_found": body["not_found"]}
                    if answerable:
                        rank = next(
                            (
                                r["rank"]
                                for r in body["retrieved"]
                                if r["filename"] == item["expected_doc"]
                                and label_matches(r["page_or_section"], item["expected_page_or_section"])
                            ),
                            None,
                        )
                        hits.append(1.0 if rank else 0.0)
                        rr.append(1.0 / rank if rank else 0.0)
                        verdict = judge(item["question"], item["expected_answer"], body["answer"])
                        acc.append(VERDICT_SCORE[verdict["verdict"]])
                        cited = any(
                            c["filename"] == item["expected_doc"]
                            and label_matches(c["page_or_section"], item["expected_page_or_section"])
                            for c in body["citations"]
                        )
                        cite.append(1.0 if cited else 0.0)
                        row.update(rank=rank, verdict=verdict["verdict"], cited=cited)
                    rows.append(row)
                modes_out[mode] = {
                    "hit_at_k": mean(hits),
                    "mrr": mean(rr),
                    "answer_accuracy": mean(acc),
                    "citation_correctness": mean(cite),
                    "fallback_accuracy": mean(fallback),
                    "latency_p50_ms": percentile(lat, 50),
                    "latency_p95_ms": percentile(lat, 95),
                }
                per_item[mode] = rows

            warm_questions = [i["question"] for i in dataset if i["answerable"]][:10]
            warm = []
            for q in warm_questions:
                started = time.perf_counter()
                resp = client.post(
                    "/api/ask", headers=headers, json={"question": q, "mode": "hybrid_rerank"}
                )
                warm.append((time.perf_counter() - started) * 1000)
                if not resp.json()["cached"]:
                    sys.exit("Expected a cache hit on the repeated question.")
            cold_ms = mean([cold_by_q[q] for q in warm_questions])
            warm_ms = mean(warm)

        results = {
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mock": mock,
            "k": top_k,
            "dataset_size": len(dataset),
            "modes": modes_out,
            "cache": {
                "cold_ms": int(round(cold_ms)),
                "warm_ms": int(round(warm_ms)),
                "speedup": round(cold_ms / warm_ms, 1) if warm_ms else 0.0,
            },
        }
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        (out_dir / "report.md").write_text(render_report(results), encoding="utf-8")
        return results
    finally:
        try:
            from app.runtime import reset_runtime

            reset_runtime()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


def render_report(results: dict) -> str:
    label = "Mock run (deterministic offline models)" if results["mock"] else "Real run (Gemini API)"
    pct = lambda v: f"{v * 100:.1f}%"  # noqa: E731
    head = (
        "| Mode | Hit@k | MRR | Answer accuracy | Citation correctness | Fallback accuracy | p50 ms | p95 ms |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    rows = "".join(
        f"| `{m}` | {pct(v['hit_at_k'])} | {v['mrr']:.3f} | {pct(v['answer_accuracy'])} | "
        f"{pct(v['citation_correctness'])} | {pct(v['fallback_accuracy'])} | "
        f"{v['latency_p50_ms']} | {v['latency_p95_ms']} |\n"
        for m, v in results["modes"].items()
    )
    cache = results["cache"]
    return (
        f"# DocuMind evaluation report\n\n"
        f"- **{label}**\n"
        f"- Generated: {results['generated_at']}\n"
        f"- Questions: {results['dataset_size']} (k = {results['k']})\n\n"
        f"{head}{rows}\n"
        f"Answer cache: cold {cache['cold_ms']} ms vs warm {cache['warm_ms']} ms "
        f"({cache['speedup']}x faster on repeat questions).\n\n"
        "Hit@k and MRR are measured over answerable questions; fallback accuracy covers all "
        "questions (answers when it should, declines when it should).\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--mock", action="store_true", help="use deterministic fake models (no API key)")
    parser.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    parser.add_argument("--out", type=Path, default=EVAL_DIR / "results", help="output directory")
    args = parser.parse_args()
    results = run(args.mock, args.limit, args.out)
    print((args.out / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
