import pytest
import asyncio
import json
from unittest.mock import patch, AsyncMock
from app.core.worker_task import _process_job
from app.core.jobs import JOB_POLL_EMAILS
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_process_job_poll_emails_success(db: AsyncSession):
    with patch("app.core.worker_task.poll_emails", AsyncMock()) as mock_poll, \
         patch("app.core.worker_task.AsyncSessionLocal", return_value=db):
         
        job = {"type": JOB_POLL_EMAILS}
        await _process_job(json.dumps(job))
        mock_poll.assert_called_once_with(db)

@pytest.mark.asyncio
async def test_process_job_poll_emails_timeout(db: AsyncSession):
    async def slow_poll(db_session):
        await asyncio.sleep(10)
        
    with patch("app.core.worker_task.poll_emails", side_effect=slow_poll), \
         patch("app.core.worker_task.AsyncSessionLocal", return_value=db), \
         patch("app.core.worker_task.asyncio.wait_for", side_effect=asyncio.TimeoutError()), \
         patch("app.core.worker_task.logger.error") as mock_log_error:
         
        job = {"type": JOB_POLL_EMAILS}
        await _process_job(json.dumps(job))
        
        mock_log_error.assert_called_with("Email polling timed out after 120 seconds.")
