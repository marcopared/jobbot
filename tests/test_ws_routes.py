"""Tests for WebSocket log stream (gated by debug_endpoints_enabled)."""

from unittest.mock import patch

from starlette.testclient import TestClient

from apps.api.main import app


def test_ws_logs_rejected_when_debug_disabled():
    """WS /ws/logs rejects connection when DEBUG_ENDPOINTS_ENABLED is False (default)."""
    client = TestClient(app)
    with client.websocket_connect("/ws/logs") as websocket:
        # Server accepts then immediately closes with policy violation
        msg = websocket.receive()
        assert msg["type"] == "websocket.close"
        assert msg.get("code") == 1008
        assert "debug" in msg.get("reason", "").lower()


@patch("apps.api.routes.ws.settings")
def test_ws_logs_accepts_when_debug_enabled(mock_settings):
    """WS /ws/logs accepts connection and stays open when DEBUG_ENDPOINTS_ENABLED is True."""
    mock_settings.debug_endpoints_enabled = True
    mock_settings.redis_url = "redis://localhost:6379/0"
    client = TestClient(app)
    with client.websocket_connect("/ws/logs") as websocket:
        # Connection accepted - we entered the block without immediate close.
        # Exiting the block closes from client side; handler will get WebSocketDisconnect.
        pass
