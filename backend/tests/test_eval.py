from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_run_eval_mock_writes_reports(tmp_path: Path) -> None:
    out = tmp_path / "results"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "eval" / "run_eval.py"),
            "--mock",
            "--limit",
            "8",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=240,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    results = json.loads((out / "results.json").read_text())
    assert results["mock"] is True and results["dataset_size"] == 8
    assert set(results["modes"]) == {"vector", "hybrid", "hybrid_rerank"}
    for metrics in results["modes"].values():
        assert set(metrics) == {
            "hit_at_k",
            "mrr",
            "answer_accuracy",
            "citation_correctness",
            "fallback_accuracy",
            "latency_p50_ms",
            "latency_p95_ms",
        }
        assert all(
            0 <= metrics[k] <= 1
            for k in ("hit_at_k", "mrr", "answer_accuracy", "fallback_accuracy")
        )
    assert results["cache"]["warm_ms"] <= results["cache"]["cold_ms"]
    report = (out / "report.md").read_text()
    assert "hybrid_rerank" in report and "Mock run" in report


def test_dataset_is_well_formed() -> None:
    data = json.loads((ROOT / "eval" / "dataset.json").read_text())
    assert len(data) >= 30
    assert sum(1 for d in data if not d["answerable"]) >= 5
    assert len({d["id"] for d in data}) == len(data)
    for d in data:
        assert {
            "question",
            "expected_answer",
            "expected_doc",
            "expected_page_or_section",
            "answerable",
        } <= set(d)
