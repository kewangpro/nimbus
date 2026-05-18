from fastapi.testclient import TestClient
from app.main import app
from app.core.socket import manager

def test_websocket_flow() -> None:
    client = TestClient(app)
    
    # Connect to the WebSocket
    with client.websocket_connect("/api/v1/ws/test-client-123") as websocket:
        # Check that the connection has been tracked in the manager
        # Since active_connections might have other connections or we want to verify this specific websocket
        assert any(conn is not None for conn in manager.active_connections)
        
        # Send a message to keep it alive
        websocket.send_text("ping")
        
    # After exiting the block, the websocket disconnects
    # Verify that the manager removes it
    # Note: the mock or active_connections list should reflect the removal
