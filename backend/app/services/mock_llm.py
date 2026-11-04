"""Deterministic offline stand-in for the model provider (tests, CI, eval --mock)."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator

from app.services.llm import NOT_FOUND_SENTINEL, ContextPassage, LLMClient
from app.services.textutil import split_sentences, tokenize

DIMS = 512
_PRONOUNS = {"it", "its", "that", "this", "they", "them", "those", "these", "he", "she"}


def _bucket(token: str) -> tuple[int, float]:
    digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
    value = int.from_bytes(digest, "big")
    return value % DIMS, 1.0 if (value >> 40) & 1 else -1.0


def embed_text(text: str) -> list[float]:
    """Hashed bag of stemmed words plus bigrams, L2-normalised."""
    tokens = tokenize(text)
    grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
    vec = [0.0] * DIMS
    counts: dict[str, int] = {}
    for g in grams:
        counts[g] = counts.get(g, 0) + 1
    for gram, count in counts.items():
        idx, sign = _bucket(gram)
        weight = (1.0 + math.log(count)) * (0.6 if "_" in gram else 1.0)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def distinctive_terms(question: str, passage_sets: list[set[str]]) -> list[str]:
    """Question terms minus those found in nearly every passage (e.g. a product name).

    Mirrors what a real model does: a company name appearing everywhere says nothing about
    whether the passages answer the question.
    """
    terms = list(dict.fromkeys(tokenize(question)))
    if len(passage_sets) < 3:
        return terms
    common = {t for t in terms if sum(t in s for s in passage_sets) >= 0.8 * len(passage_sets)}
    return [t for t in terms if t not in common] or terms


def coverage(terms: list[str], passage_tokens: set[str]) -> float:
    """Fraction of the given terms present in the passage."""
    return len(set(terms) & passage_tokens) / len(terms) if terms else 0.0


class MockLLM(LLMClient):
    """Extractive, deterministic implementation of every LLM task."""

    def __init__(self) -> None:
        super().__init__()
        self.embedding_model = "mock-embedding-v1"
        self.chat_model = "mock-chat-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls["embed"] += 1
        return [embed_text(t) for t in texts]

    def rewrite_question(self, question: str, history: list[tuple[str, str]]) -> str:
        self.calls["rewrite"] += 1
        last_user = next((c for r, c in reversed(history) if r == "user"), "")
        words = re.findall(r"[a-z]+", question.lower())
        needs_context = len(tokenize(question)) <= 3 or any(w in _PRONOUNS for w in words)
        if last_user and needs_context:
            return f"{question.strip().rstrip('?')} (regarding: {last_user.strip()})"
        return question

    def rerank_scores(self, question: str, passages: list[str]) -> list[float] | None:
        self.calls["rerank"] += 1
        sets = [set(tokenize(p)) for p in passages]
        terms = distinctive_terms(question, sets)
        return [round(10.0 * coverage(terms, s) ** 1.25, 2) for s in sets]

    def answer_stream(
        self, question: str, passages: list[ContextPassage], history: list[tuple[str, str]]
    ) -> Iterator[str]:
        self.calls["answer"] += 1
        sets = [set(tokenize(p.text)) for p in passages]
        terms = distinctive_terms(question, sets)
        present = {t for t in terms if any(t in s for s in sets)}
        if not terms or len(present) / len(terms) < 0.6:
            yield NOT_FOUND_SENTINEL
            return
        q_terms = set(terms)
        needed = 1 if len(q_terms) <= 2 else 2
        scored: list[tuple[int, int, str, int]] = []
        for p in passages:
            for pos, sentence in enumerate(split_sentences(p.text)):
                overlap = len(q_terms & set(tokenize(sentence)))
                if overlap >= needed:
                    scored.append((overlap, -pos, sentence, p.id))
        if not scored:
            yield NOT_FOUND_SENTINEL
            return
        scored.sort(key=lambda s: (-s[0], -s[1]))
        picked = scored[:2]
        text = " ".join(f"{s.rstrip('.')}. [{pid}]" for _, _, s, pid in picked)
        yield from re.findall(r"\S+\s*", text)

    def judge(self, question: str, expected: str, answer: str) -> dict:
        self.calls["judge"] += 1
        said_not_found = "couldn't find" in answer.lower() or NOT_FOUND_SENTINEL in answer
        if expected.lower().startswith("not found"):
            ok = said_not_found
            return {
                "verdict": "correct" if ok else "incorrect",
                "reason": "Declined as expected." if ok else "Answered an unanswerable question.",
            }
        if said_not_found:
            return {"verdict": "incorrect", "reason": "Said the answer was not found."}
        exp = set(tokenize(expected))
        if not exp:
            return {"verdict": "incorrect", "reason": "No reference terms."}
        hit = len(exp & set(tokenize(answer))) / len(exp)
        verdict = "correct" if hit >= 0.7 else "partially" if hit >= 0.35 else "incorrect"
        return {"verdict": verdict, "reason": f"{hit:.0%} of reference terms present."}
