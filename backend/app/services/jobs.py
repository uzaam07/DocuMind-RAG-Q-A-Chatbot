"""Ingestion job dispatch: durable Redis/RQ when configured, local task fallback otherwise."""

from __future__ import annotations

from fastapi import BackgroundTasks

from app.config import get_settings
from app.services.ingest import ingest_document


def schedule_ingestion(background: BackgroundTasks, document_id: str) -> str:
    settings = get_settings()
    redis_url = settings.redis_url.strip()
    if redis_url:
        try:
            from redis import Redis
            from rq import Queue
            connection = Redis.from_url(redis_url)
            queue = Queue("documind-ingestion", connection=connection, default_timeout=1800)
            job = queue.enqueue(ingest_document, document_id, job_timeout=1800, result_ttl=86400)
            return job.id
        except Exception:
            # Keep local functionality available during a Redis outage. The API logs the
            # fallback so operators can distinguish durable and in-process processing.
            import logging
            logging.getLogger(__name__).exception(
                "Redis queue unavailable; using local background task"
            )
            background.add_task(ingest_document, document_id)
            return "local-fallback"
    background.add_task(ingest_document, document_id)
    return "local-background-task"
