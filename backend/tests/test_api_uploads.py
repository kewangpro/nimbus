import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_upload_file_success(client: AsyncClient, normal_user_token_headers: dict) -> None:
    # Prepare dummy file content
    file_content = b"test file content"
    files = {"file": ("test_doc.txt", file_content, "text/plain")}
    
    # Mock minio client.put_object method
    with patch("app.api.v1.endpoints.uploads.client") as mock_minio_client:
        mock_minio_client.put_object = MagicMock()
        
        response = await client.post(
            "/api/v1/uploads/",
            headers=normal_user_token_headers,
            files=files
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert data["filename"] == "test_doc.txt"
        assert "storage_name" in data
        assert data["storage_name"].endswith(".txt")
        
        # Verify minio client put_object was called
        mock_minio_client.put_object.assert_called_once()

@pytest.mark.asyncio
async def test_upload_file_error(client: AsyncClient, normal_user_token_headers: dict) -> None:
    # Prepare dummy file content
    file_content = b"test file content"
    files = {"file": ("test_doc.txt", file_content, "text/plain")}
    
    # Mock minio client.put_object to raise an Exception
    with patch("app.api.v1.endpoints.uploads.client") as mock_minio_client:
        mock_minio_client.put_object = MagicMock(side_effect=Exception("MinIO is down"))
        
        response = await client.post(
            "/api/v1/uploads/",
            headers=normal_user_token_headers,
            files=files
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["detail"] == "Could not upload file"

def test_init_storage_bucket_exists() -> None:
    from app.core.storage import init_storage
    
    with patch("app.core.storage.client") as mock_client:
        mock_client.bucket_exists = MagicMock(return_value=True)
        mock_client.make_bucket = MagicMock()
        
        init_storage()
        
        mock_client.bucket_exists.assert_called_once()
        mock_client.make_bucket.assert_not_called()

def test_init_storage_bucket_does_not_exist() -> None:
    from app.core.storage import init_storage
    
    with patch("app.core.storage.client") as mock_client:
        mock_client.bucket_exists = MagicMock(return_value=False)
        mock_client.make_bucket = MagicMock()
        
        init_storage()
        
        mock_client.bucket_exists.assert_called_once()
        mock_client.make_bucket.assert_called_once()

