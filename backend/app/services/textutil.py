"""Small text helpers shared by BM25, the mock models and citation highlighting."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")

STOPWORDS = frozenset(
    """
    a about above after again all also am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from
    further had has have having he her here hers him his how i if in into is it its just me
    more most my no nor not of off on once only or other our out over own same she should so
    some such than that the their them then there these they this those through to too under
    until up very was we were what when where which while who whom why will with would you
    your yours
    """.split()
)


def stem(word: str) -> str:
    """Very light suffix stripping, enough to match plurals and simple verb forms."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str, *, keep_stopwords: bool = False) -> list[str]:
    """Lower-case, split into words, drop stopwords and stem."""
    words = _WORD.findall(text.lower())
    return [stem(w) for w in words if keep_stopwords or w not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    """Split text into trimmed, non-empty sentences."""
    return [s.strip() for s in _SENTENCE.split(text) if s and s.strip()]


def best_sentence(question: str, text: str) -> str | None:
    """Return the sentence in text that shares the most terms with the question."""
    q_terms = set(tokenize(question))
    if not q_terms:
        return None
    best: tuple[int, str] | None = None
    for sentence in split_sentences(text):
        overlap = len(q_terms & set(tokenize(sentence)))
        if overlap and (best is None or overlap > best[0]):
            best = (overlap, sentence)
    return best[1] if best else None


def normalize_question(question: str) -> str:
    """Canonical form used for cache keys."""
    return re.sub(r"\s+", " ", question.strip().lower())
