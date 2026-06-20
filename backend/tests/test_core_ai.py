import pytest
from unittest.mock import patch
from app.core import ai

@pytest.mark.asyncio
async def test_generate_completion_success():
    with patch("app.core.ai._sync_generate", return_value="AI Response") as mock_sync_gen:
        res = await ai.generate_completion("Test prompt", "System prompt")
        assert res == "AI Response"
        mock_sync_gen.assert_called_once_with(
            "Test prompt", "System prompt", ai.CHAT_MODEL
        )


@pytest.mark.asyncio
async def test_generate_completion_fallback():
    # Simulate primary model failing and fallback model succeeding
    def side_effect(prompt, system_prompt, model_name):
        if model_name == ai.CHAT_MODEL:
            raise ValueError("GPU out of memory")
        return "Fallback Response"

    with patch("app.core.ai._sync_generate", side_effect=side_effect) as mock_sync_gen:
        res = await ai.generate_completion("Test prompt", "System prompt")
        assert res == "Fallback Response"
        assert mock_sync_gen.call_count == 2
        # First call with CHAT_MODEL
        mock_sync_gen.assert_any_call("Test prompt", "System prompt", ai.CHAT_MODEL)
        # Second call with FAST_MODEL
        mock_sync_gen.assert_any_call("Test prompt", "System prompt", ai.FAST_MODEL)


@pytest.mark.asyncio
async def test_generate_completion_all_fail():
    with patch("app.core.ai._sync_generate", side_effect=ValueError("GPU failure")):
        res = await ai.generate_completion("Test prompt", "System prompt")
        assert res is None


def test_parse_json_robust():
    # Valid JSON
    assert ai.parse_json_robust('{"key": "value"}') == {"key": "value"}
    # Single quotes and Python keywords
    assert ai.parse_json_robust("{'key': 'value', 'flag': null}") == {"key": "value", "flag": None}
    # Embedded JSON with text
    assert ai.parse_json_robust('Here is the json: {"key": "value"} and text') == {"key": "value"}
    # Multiple objects
    assert ai.parse_json_robust('{"a": 1} {"b": 2}') == [{"a": 1}, {"b": 2}]
