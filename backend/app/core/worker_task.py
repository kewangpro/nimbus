import asyncio
import json
import logging
from redis.asyncio import Redis

from app.core.config import settings
from app.core.jobs import QUEUE_NAME, JOB_BACKFILL_EMBEDDINGS, JOB_POLL_EMAILS
from app.core import ai
from app.core.email_polling import poll_emails
from app.crud import crud_embedding, crud_issue
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

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
        logger.error("Invalid job payload")
        return

    job_type = job.get("type")
    if job_type == JOB_BACKFILL_EMBEDDINGS:
        total = await _backfill_embeddings()
        logger.info(f"Backfill completed. Updated {total} issues.")
        return

    if job_type == JOB_POLL_EMAILS:
        async with AsyncSessionLocal() as db:
            try:
                # Wrap email polling in wait_for to prevent aioimaplib from hanging indefinitely on dead connections
                await asyncio.wait_for(poll_emails(db), timeout=120)
                logger.info("Email polling completed.")
            except asyncio.TimeoutError:
                logger.error("Email polling timed out after 120 seconds.")
        return

    logger.warning(f"Unknown job type: {job_type}")


async def run_worker() -> None:
    logger.info("Nimbus background worker task started.")
    while True:
        try:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            try:
                while True:
                    result = await redis.blpop(QUEUE_NAME, timeout=5)
                    if not result:
                        continue
                    _, raw = result
                    await _process_job(raw)
            finally:
                await redis.aclose()
        except (ConnectionError, ConnectionRefusedError, OSError) as e:
            logger.error(f"Redis connection error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Worker task cancelled.")
            break
        except Exception as e:
            logger.error(f"Unexpected worker error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)
