"""
FinAI Backend — Real-Time WebSocket Event System
=================================================
Manages WebSocket connections and broadcasts events to all connected clients.

Event types:
  - data_updated     — dataset modified or new data ingested
  - alert_triggered  — monitoring alert fired
  - upload_complete  — smart-upload finished processing
  - analysis_ready   — orchestrator pipeline completed
  - action_proposed  — decision engine proposed new action

Usage:
  from app.services.realtime import realtime_manager
  await realtime_manager.emit("upload_complete", {"dataset_id": 42, "filename": "jan.xlsx"})
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Valid event types
EVENT_TYPES = {
    "data_updated",
    "alert_triggered",
    "upload_complete",
    "analysis_ready",
    "action_proposed",
}


class ConnectionManager:
    """Manages WebSocket connections and broadcasts real-time events."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._event_log: List[Dict[str, Any]] = []  # last N events for replay
        self._max_log: int = 100

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection and send current status."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WS realtime client connected (total: %d)", self.connection_count)

        # Send welcome + current system status
        await self._send_json(websocket, {
            "type": "connected",
            "payload": {
                "message": "Connected to FinAI real-time event stream",
                "active_connections": self.connection_count,
            },
            "timestamp": _now_iso(),
        })

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected client."""
        self._connections.discard(websocket)
        logger.info("WS realtime client disconnected (total: %d)", self.connection_count)

    async def handle_message(self, websocket: WebSocket, data: dict):
        """Handle incoming messages from clients (ping/pong, subscribe)."""
        msg_type = data.get("type", "")

        if msg_type == "ping":
            await self._send_json(websocket, {
                "type": "pong",
                "payload": {},
                "timestamp": _now_iso(),
            })
        elif msg_type == "get_status":
            await self._send_json(websocket, {
                "type": "status",
                "payload": {
                    "active_connections": self.connection_count,
                    "recent_events": len(self._event_log),
                },
                "timestamp": _now_iso(),
            })
        elif msg_type == "get_history":
            # Send recent event log
            limit = min(data.get("limit", 20), self._max_log)
            await self._send_json(websocket, {
                "type": "event_history",
                "payload": {"events": self._event_log[-limit:]},
                "timestamp": _now_iso(),
            })
        else:
            await self._send_json(websocket, {
                "type": "error",
                "payload": {"message": f"Unknown message type: {msg_type}"},
                "timestamp": _now_iso(),
            })

    async def emit(self, event_type: str, payload: Optional[Dict[str, Any]] = None):
        """
        Broadcast an event to ALL connected WebSocket clients.

        Args:
            event_type: One of EVENT_TYPES (data_updated, alert_triggered, etc.)
            payload: Event-specific data dict
        """
        if event_type not in EVENT_TYPES:
            logger.warning("Unknown event type: %s (broadcasting anyway)", event_type)

        event = {
            "type": event_type,
            "payload": payload or {},
            "timestamp": _now_iso(),
        }

        # Store in event log
        self._event_log.append(event)
        if len(self._event_log) > self._max_log:
            self._event_log = self._event_log[-self._max_log:]

        # Broadcast to all connected clients
        if not self._connections:
            logger.debug("No WS clients to broadcast %s event to", event_type)
            return

        stale: List[WebSocket] = []
        for ws in self._connections:
            try:
                await self._send_json(ws, event)
            except Exception:
                stale.append(ws)

        # Clean up dead connections
        for ws in stale:
            self._connections.discard(ws)

        logger.info(
            "Broadcast %s to %d clients (removed %d stale)",
            event_type,
            self.connection_count,
            len(stale),
        )

    async def broadcast(self, message: Dict[str, Any]):
        """Send a raw message dict to all connected clients."""
        stale: List[WebSocket] = []
        for ws in self._connections:
            try:
                await self._send_json(ws, message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)

    async def _send_json(self, ws: WebSocket, data: dict):
        """Send JSON to a single WebSocket, catching errors."""
        try:
            await ws.send_json(data)
        except Exception:
            raise

    def get_status(self) -> dict:
        """Return manager status for /health or /status endpoints."""
        return {
            "active_connections": self.connection_count,
            "event_log_size": len(self._event_log),
            "supported_events": sorted(EVENT_TYPES),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Module-level singleton ──
realtime_manager = ConnectionManager()
