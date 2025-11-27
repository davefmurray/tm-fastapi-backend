"""
WebSocket Manager (Tier 5)

Manages WebSocket connections for real-time dashboard updates.
Supports broadcasting live GP metrics to connected clients.
"""

import asyncio
from typing import Dict, List, Set, Optional, Any
from fastapi import WebSocket
from datetime import datetime
import json


class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.

    Features:
    - Multiple connection tracking
    - Channel-based subscriptions (dashboard, tech, ro)
    - Broadcast to all or specific channels
    - Connection health monitoring
    """

    def __init__(self):
        # All active connections
        self.active_connections: List[WebSocket] = []

        # Connections by channel
        self.channels: Dict[str, Set[WebSocket]] = {
            "dashboard": set(),      # Main dashboard metrics
            "tech_performance": set(),  # Tech leaderboard
            "ro_feed": set(),        # Live RO updates
            "alerts": set()          # GP alerts/warnings
        }

        # Connection metadata
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, channels: List[str] = None):
        """
        Accept new WebSocket connection and subscribe to channels.

        Args:
            websocket: The WebSocket connection
            channels: List of channels to subscribe to (default: dashboard)
        """
        await websocket.accept()
        self.active_connections.append(websocket)

        # Default to dashboard channel
        if not channels:
            channels = ["dashboard"]

        # Subscribe to channels
        for channel in channels:
            if channel in self.channels:
                self.channels[channel].add(websocket)

        # Store connection metadata
        self.connection_info[websocket] = {
            "connected_at": datetime.now().isoformat(),
            "channels": channels,
            "client_ip": websocket.client.host if websocket.client else "unknown"
        }

        print(f"[WS] Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove connection from all channels and active list."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Remove from all channels
        for channel in self.channels.values():
            channel.discard(websocket)

        # Remove metadata
        self.connection_info.pop(websocket, None)

        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")

    async def send_personal(self, message: dict, websocket: WebSocket):
        """Send message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"[WS] Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to ALL connected clients."""
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Broadcast error: {e}")
                disconnected.append(connection)

        # Clean up dead connections
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast message to specific channel subscribers."""
        if channel not in self.channels:
            return

        disconnected = []
        message["channel"] = channel
        message["timestamp"] = datetime.now().isoformat()

        for connection in self.channels[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WS] Channel broadcast error ({channel}): {e}")
                disconnected.append(connection)

        # Clean up dead connections
        for ws in disconnected:
            self.disconnect(ws)

    async def send_dashboard_update(self, metrics: dict):
        """Send dashboard metrics update to subscribers."""
        await self.broadcast_to_channel("dashboard", {
            "type": "dashboard_update",
            "data": metrics
        })

    async def send_tech_update(self, tech_data: list):
        """Send tech performance update to subscribers."""
        await self.broadcast_to_channel("tech_performance", {
            "type": "tech_update",
            "data": tech_data
        })

    async def send_ro_update(self, ro_data: dict):
        """Send RO feed update to subscribers."""
        await self.broadcast_to_channel("ro_feed", {
            "type": "ro_update",
            "data": ro_data
        })

    async def send_alert(self, alert: dict):
        """Send alert to all alert channel subscribers."""
        await self.broadcast_to_channel("alerts", {
            "type": "alert",
            "severity": alert.get("severity", "info"),
            "data": alert
        })

    def get_status(self) -> dict:
        """Get current connection status."""
        return {
            "total_connections": len(self.active_connections),
            "channels": {
                channel: len(connections)
                for channel, connections in self.channels.items()
            },
            "connections": [
                {
                    "client_ip": info.get("client_ip"),
                    "connected_at": info.get("connected_at"),
                    "channels": info.get("channels", [])
                }
                for info in self.connection_info.values()
            ]
        }


# Singleton instance
manager = ConnectionManager()


def get_ws_manager() -> ConnectionManager:
    """Get the singleton WebSocket manager."""
    return manager
