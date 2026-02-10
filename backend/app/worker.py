import asyncio
import json

from redis.asyncio import Redis

from app.core.config import settings
from app.core.jobs import QUEUE_NAME, JOB_BACKFILL_EMBEDDINGS
from app.core import ai
from app.crud import crud_embedding, crud_issue
from app.db.session import AsyncSessionLocal


async def _backfill_embeddings() -> int:
    count = 0
    async with AsyncSessionLocal() as db:
        page_size = 200
        skip = 0
        while True:
            issues = await crud_issue.get_multi(db, skip=skip, limit=page_size)
            if not issues:
                break
            for issue in issues:
                full_text = f"{issue.title} {issue.description or ''}"
                content_hash = crud_issue.get_content_hash(full_text)
                embedding = await ai.generate_embedding(full_text)
                if embedding:
                    await crud_embedding.create_or_update(
                        db, issue_id=issue.id, embedding=embedding, content_hash=content_hash
                    )
                    count += 1
            if len(issues) < page_size:
                break
            skip += page_size
    return count


async def _process_job(raw: str) -> None:
    try:
        job = json.loads(raw)
    except Exception:
        print("Invalid job payload")
        return

    job_type = job.get("type")
    if job_type == JOB_BACKFILL_EMBEDDINGS:
        total = await _backfill_embeddings()
        print(f"Backfill completed. Updated {total} issues.")
        return

    print(f"Unknown job type: {job_type}")


async def run_worker() -> None:
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    print("Nimbus worker started. Waiting for jobs...")
    try:
        while True:
            result = await redis.blpop(QUEUE_NAME, timeout=5)
            if not result:
                continue
            _, raw = result
            await _process_job(raw)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(run_worker())
