import json
import uuid
from typing import Any, Dict

from redis.asyncio import Redis

from app.core.config import settings


QUEUE_NAME = "nimbus:jobs"
JOB_BACKFILL_EMBEDDINGS = "backfill_embeddings"
JOB_POLL_EMAILS = "poll_emails"


def _redis_client() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def enqueue_job(job_type: str, payload: Dict[str, Any]) -> str:
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "type": job_type, "payload": payload}
    redis = _redis_client()
    try:
        await redis.rpush(QUEUE_NAME, json.dumps(job))
    finally:
        await redis.aclose()
    return job_id


async def is_job_type_queued(job_type: str) -> bool:
    """Check if a job of a specific type is already in the queue."""
    redis = _redis_client()
    try:
        # Get all jobs from the queue (range 0 to -1)
        jobs = await redis.lrange(QUEUE_NAME, 0, -1)
        for raw in jobs:
            try:
                job = json.loads(raw)
                if job.get("type") == job_type:
                    return True
            except Exception:
                continue
        return False
    finally:
        await redis.aclose()
