import pytest
from app.core.email_processor import email_processor
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_success(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '{"title": "Fix bug", "description": "Bug in app", "priority": "high", "due_date": "2024-12-31"}'
    
    tasks = await email_processor.extract_task("Bug Report", "There is a bug in the app.")
    
    assert tasks is not None
    assert isinstance(tasks, list)
    assert tasks[0]["title"] == "Fix bug"
    assert tasks[0]["priority"] == "high"
    assert tasks[0]["due_date"] == "2024-12-31"

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_no_response(mock_ai_generate) -> None:
    mock_ai_generate.return_value = None
    
    tasks = await email_processor.extract_task("Subject", "Body")
    assert tasks is None

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_invalid_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = "This is not json."
    
    tasks = await email_processor.extract_task("Subject", "Body")
    assert tasks is None

@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_embedded_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = 'Here is the task: {"title": "Test"} and some more text.'
    
    tasks = await email_processor.extract_task("Subject", "Body")
    assert tasks is not None
    assert isinstance(tasks, list)
    assert tasks[0]["title"] == "Test"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_array_response(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    [
      {"title": "Alert 1", "priority": "high"},
      {"title": "Alert 2", "priority": "low"}
    ]
    '''
    tasks = await email_processor.extract_task("Subject", "Body")
    assert isinstance(tasks, list)
    assert len(tasks) == 2
    assert tasks[0]["title"] == "Alert 1"
    assert tasks[1]["title"] == "Alert 2"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_truncated_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    [
      {"title": "Alert 1", "priority": "high"},
      {"title": "Alert 2", "priority": "low"
    '''
    tasks = await email_processor.extract_task("Subject", "Body")
    assert isinstance(tasks, list)
    assert tasks[0]["title"] == "Alert 1"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_markdown_wrapped_json(mock_ai_generate) -> None:
    mock_ai_generate.return_value = '''
    ```json
    {"title": "Task inside Markdown", "priority": "medium"}
    ```
    '''
    tasks = await email_processor.extract_task("Subject", "Body")
    assert tasks is not None
    assert isinstance(tasks, list)
    assert tasks[0]["title"] == "Task inside Markdown"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_with_comments(mock_ai_generate) -> None:
    # Test stripping of trailing comments (on separate lines or end of block)
    mock_ai_generate.return_value = '{\n"title": "Task",\n"priority": "high"\n} # This is a comment'
    
    tasks = await email_processor.extract_task("Subject", "Body")
    assert tasks is not None
    assert tasks[0]["title"] == "Task"


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_single_quotes(mock_ai_generate) -> None:
    # Test ast.literal_eval fallback for single quotes
    mock_ai_generate.return_value = "{'title': 'Single Quote Task', 'due_date': null}"
    
    task = await email_processor.extract_task("Subject", "Body")
    assert isinstance(task, list)
    assert task[0]["title"] == "Single Quote Task"
    assert task[0]["due_date"] is None


@pytest.mark.asyncio
@patch("app.core.ai.generate_completion", new_callable=AsyncMock)
async def test_extract_task_empty_list(mock_ai_generate) -> None:
    # Test empty list response
    mock_ai_generate.return_value = "[]"
    
    task = await email_processor.extract_task("Subject", "Body")
    assert task == []
