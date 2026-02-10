import json
import uuid
from typing import Any, Dict

from redis.asyncio import Redis

from app.core.config import settings


QUEUE_NAME = "nimbus:jobs"
JOB_BACKFILL_EMBEDDINGS = "backfill_embeddings"


def _redis_client() -> Redis:
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def enqueue_job(job_type: str, payload: Dict[str, Any]) -> str:
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "type": job_type, "payload": payload}
    redis = _redis_client()
    await redis.rpush(QUEUE_NAME, json.dumps(job))
    await redis.aclose()
    return job_id
