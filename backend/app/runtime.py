"""Reset every process-wide cache (used by tests and the eval harness)."""

from __future__ import annotations

import contextlib


def reset_runtime() -> None:
    """Drop cached settings, DB engine, Chroma client, LLM client and BM25 indexes."""
    from app import config, db
    from app.services import bm25_index, cache, llm, vectorstore

    with contextlib.suppress(Exception):  # the engine may not exist yet
        db.get_engine().dispose()
    config.get_settings.cache_clear()
    db.get_engine.cache_clear()
    db.get_sessionmaker.cache_clear()
    vectorstore.get_client.cache_clear()
    vectorstore.get_collection.cache_clear()
    llm.get_llm.cache_clear()
    bm25_index.clear()
    cache.reset_counters()
