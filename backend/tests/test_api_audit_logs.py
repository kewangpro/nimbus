import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_audit

@pytest.mark.asyncio
async def test_get_audit_logs(client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession):
    # Setup some test logs
    # Assume the normal_user_token_headers created a user, but we'll just log something.
    await crud_audit.log_action(db, "test.action", None, "test", None, {"key": "val"})
    
    # Query logs
    r = await client.get("/api/v1/audit-logs/", headers=normal_user_token_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["action"] == "test.action"

@pytest.mark.asyncio
async def test_get_audit_stats(client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession):
    # Setup action
    await crud_audit.log_action(db, "stat.action")
    
    # Query stats
    r = await client.get("/api/v1/audit-logs/stats", headers=normal_user_token_headers)
    assert r.status_code == 200
    data = r.json()
    assert "action_counts" in data
    assert "stat.action" in data["action_counts"]
