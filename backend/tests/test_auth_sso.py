import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.config import settings

@pytest.mark.asyncio
async def test_auth_login_redirect(client: AsyncClient):
    # Test Google Login Redirect
    with patch("app.core.config.settings.GOOGLE_CLIENT_ID", "test-google-id"):
        response = await client.get("/api/v1/auth/login/gmail", follow_redirects=False)
        assert response.status_code == 307
        assert "accounts.google.com" in response.headers["location"]

    # Test Outlook Login Redirect
    with patch("app.core.config.settings.MICROSOFT_CLIENT_ID", "test-ms-id"):
        response = await client.get("/api/v1/auth/login/outlook", follow_redirects=False)
        assert response.status_code == 307
        assert "login.microsoftonline.com" in response.headers["location"]

@pytest.mark.asyncio
async def test_auth_callback_gmail(client: AsyncClient):
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {
        "access_token": "mock-access-token",
        "refresh_token": "mock-refresh-token",
        "expires_in": 3600
    }

    mock_userinfo_response = MagicMock()
    mock_userinfo_response.status_code = 200
    mock_userinfo_response.json.return_value = {
        "email": "test@gmail.com",
        "name": "Test User",
        "sub": "google-id-123"
    }

    with patch("app.api.v1.endpoints.auth.HttpxAsyncClient") as mock_client_cls:

        # Create an instance that returns our mock responses
        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_token_response
        mock_client_instance.get.return_value = mock_userinfo_response
        
        # Configure the context manager behavior
        mock_client_cls.return_value.__aenter__.return_value = mock_client_instance
        
        with patch("app.core.config.settings.GOOGLE_CLIENT_ID", "test-id"), \
             patch("app.core.config.settings.GOOGLE_CLIENT_SECRET", "test-secret"):
            
            response = await client.get("/api/v1/auth/callback/gmail?code=mock-code")
            assert response.status_code == 307
            assert "token=" in response.headers["location"]

        assert "/login" in response.headers["location"]
