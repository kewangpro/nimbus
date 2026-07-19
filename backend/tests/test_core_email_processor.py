import pytest
from app.core.email_processor import email_processor
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_success(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '{"title": "Fix bug", "description": "Bug in app", "priority": "high", "due_date": "2024-12-31"}'
    
    task = await email_processor.extract_task("Bug Report", "There is a bug in the app.")
    
    assert task is not None
    assert isinstance(task, dict)
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
    assert isinstance(task, dict)
    assert task["title"] == "Test"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_array_response(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    [
      {"title": "Alert 1", "priority": "high"},
      {"title": "Alert 2", "priority": "low"}
    ]
    '''
    task = await email_processor.extract_task("Subject", "Body")
    assert isinstance(task, dict)
    assert task["title"] == "Alert 1"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_truncated_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    [
      {"title": "Alert 1", "priority": "high"},
      {"title": "Alert 2", "priority": "low"
    '''
    task = await email_processor.extract_task("Subject", "Body")
    assert isinstance(task, dict)
    assert task["title"] == "Alert 1"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_markdown_wrapped_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    ```json
    {"title": "Task inside Markdown", "priority": "medium"}
    ```
    '''
    task = await email_processor.extract_task("Subject", "Body")
    assert task is not None
    assert isinstance(task, dict)
    assert task["title"] == "Task inside Markdown"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_with_comments(mock_ai_generate) -> None:
    # Test stripping of trailing comments (on separate lines or end of block)
    mock_ai_generate.return_value = '{\n"title": "Task",\n"priority": "high"\n} # This is a comment'
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task is not None
    assert isinstance(task, dict)
    assert task["title"] == "Task"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_single_quotes(mock_ai_generate) -> None:
    # Test ast.literal_eval fallback for single quotes
    mock_ai_generate.return_value = "{'title': 'Single Quote Task', 'due_date': null}"
    
    task = await email_processor.extract_task("Subject", "Body")
    assert isinstance(task, dict)
    assert task["title"] == "Single Quote Task"
    assert task["due_date"] is None


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_empty_list(mock_ai_generate) -> None:
    # Test empty list response
    mock_ai_generate.return_value = "[]"
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task == {}


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_ignored_ad_or_newsletter(mock_ai_generate) -> None:
    # Test empty dict response indicating ignored newsletter
    mock_ai_generate.return_value = "{}"
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task == {}
