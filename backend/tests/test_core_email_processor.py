import pytest
from app.core.email_processor import email_processor
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_success(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '{"title": "Fix bug", "description": "Bug in app", "priority": "high", "due_date": "2024-12-31"}'
    
    task = await email_processor.extract_task("Bug Report", "There is a bug in the app.")
    
    assert task is not None
    assert task["title"] == "Fix bug"
    assert task["priority"] == "high"
    assert task["due_date"] == "2024-12-31"

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_no_response(mock_ai_generate) -> None:
    mock_ai_generate.return_value = None
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task is None

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_invalid_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = "This is not json."
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task is None

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_embedded_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = 'Here is the task: {"title": "Test"} and some more text.'
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task is not None
    assert task["title"] == "Test"
