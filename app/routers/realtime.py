"""
Real-time Dashboard Router (Tier 5)

WebSocket endpoints for live dashboard updates.
Provides real-time GP metrics streaming without polling.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from typing import Optional, List
from datetime import datetime, date

from app.services.websocket_manager import get_ws_manager
from app.services.tm_client import get_tm_client
from app.services.gp_calculator import (
    calculate_ro_true_gp,
    aggregate_tech_performance,
    to_dollars_dict,
    cents_to_dollars
)

router = APIRouter()

# Background task state
_refresh_task: Optional[asyncio.Task] = None
_refresh_interval: int = 60  # seconds


# =============================================================================
# WEBSOCKET ENDPOINTS
# =============================================================================

@router.websocket("/ws")
async def websocket_dashboard(
    websocket: WebSocket
):
    """
    Main WebSocket endpoint for real-time dashboard.

    Connect and receive live GP metrics updates.

    Usage:
        const ws = new WebSocket('ws://localhost:8000/api/realtime/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateDashboard(data);
        };

    Message types received:
        - dashboard_update: Main metrics (sales, GP%, ARO, car count)
        - tech_update: Technician performance updates
        - alert: GP alerts and warnings
        - heartbeat: Connection health check (every 30s)
    """
    manager = get_ws_manager()
    await manager.connect(websocket, channels=["dashboard", "alerts"])

    try:
        # Send initial data immediately
        await _send_initial_data(websocket)

        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong or subscription changes)
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )

                # Handle client messages
                if data.get("type") == "subscribe":
                    channels = data.get("channels", [])
                    for channel in channels:
                        if channel in manager.channels:
                            manager.channels[channel].add(websocket)

                elif data.get("type") == "unsubscribe":
                    channels = data.get("channels", [])
                    for channel in channels:
                        if channel in manager.channels:
                            manager.channels[channel].discard(websocket)

                elif data.get("type") == "ping":
                    await manager.send_personal({"type": "pong"}, websocket)

            except asyncio.TimeoutError:
                # Send heartbeat on timeout
                await manager.send_personal({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/tech")
async def websocket_tech_performance(websocket: WebSocket):
    """
    WebSocket for real-time tech performance leaderboard.

    Receives tech_update messages with per-technician metrics.
    """
    manager = get_ws_manager()
    await manager.connect(websocket, channels=["tech_performance"])

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )
                if data.get("type") == "ping":
                    await manager.send_personal({"type": "pong"}, websocket)
            except asyncio.TimeoutError:
                await manager.send_personal({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.websocket("/ws/ro-feed")
async def websocket_ro_feed(websocket: WebSocket):
    """
    WebSocket for real-time RO feed.

    Receives ro_update messages as ROs are created/modified.
    """
    manager = get_ws_manager()
    await manager.connect(websocket, channels=["ro_feed"])

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )
                if data.get("type") == "ping":
                    await manager.send_personal({"type": "pong"}, websocket)
            except asyncio.TimeoutError:
                await manager.send_personal({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat()
                }, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# =============================================================================
# REST ENDPOINTS FOR CONTROL
# =============================================================================

@router.get("/status")
async def get_realtime_status():
    """Get real-time service status and connection count."""
    manager = get_ws_manager()
    global _refresh_task, _refresh_interval

    return {
        "service": "realtime",
        "status": "active" if _refresh_task and not _refresh_task.done() else "stopped",
        "refresh_interval_seconds": _refresh_interval,
        "connections": manager.get_status()
    }


@router.post("/start")
async def start_realtime_updates(
    background_tasks: BackgroundTasks,
    interval: int = Query(60, description="Refresh interval in seconds", ge=10, le=300)
):
    """
    Start automatic real-time dashboard updates.

    This starts a background task that:
    1. Fetches current RO data
    2. Calculates True GP metrics
    3. Broadcasts to all connected WebSocket clients

    Args:
        interval: How often to refresh (10-300 seconds, default 60)
    """
    global _refresh_task, _refresh_interval

    if _refresh_task and not _refresh_task.done():
        return {
            "status": "already_running",
            "interval": _refresh_interval
        }

    _refresh_interval = interval
    _refresh_task = asyncio.create_task(_auto_refresh_loop())

    return {
        "status": "started",
        "interval": interval,
        "message": f"Real-time updates started. Broadcasting every {interval}s"
    }


@router.post("/stop")
async def stop_realtime_updates():
    """Stop automatic real-time updates."""
    global _refresh_task

    if _refresh_task:
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            pass
        _refresh_task = None

    return {"status": "stopped"}


@router.post("/broadcast")
async def trigger_broadcast():
    """
    Manually trigger a dashboard broadcast.

    Useful for forcing an immediate update after changes.
    """
    await _broadcast_dashboard_update()
    return {"status": "broadcast_sent"}


@router.post("/alert")
async def send_alert(
    message: str = Query(..., description="Alert message"),
    severity: str = Query("warning", description="Alert severity: info, warning, critical")
):
    """
    Send an alert to all connected dashboard clients.

    Use for:
    - GP% dropped below threshold
    - Unusual variance detected
    - System notifications
    """
    manager = get_ws_manager()

    await manager.send_alert({
        "message": message,
        "severity": severity,
        "timestamp": datetime.now().isoformat()
    })

    return {
        "status": "alert_sent",
        "message": message,
        "severity": severity,
        "recipients": len(manager.channels.get("alerts", set()))
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def _send_initial_data(websocket: WebSocket):
    """Send initial dashboard data when client connects."""
    try:
        client = await get_tm_client()
        today = date.today().isoformat()

        # Get today's ROs
        ros = await client.get_ros_for_period(
            start_date=today,
            end_date=today,
            status_filter=[2, 5, 6]  # WIP, POSTED, COMPLETED
        )

        if not ros:
            await websocket.send_json({
                "type": "initial_data",
                "data": {
                    "message": "No ROs found for today",
                    "date": today
                }
            })
            return

        # Calculate GP for each RO
        ro_results = []
        for ro in ros[:20]:  # Limit for initial load
            try:
                result = await calculate_ro_true_gp(ro, client)
                ro_results.append(result)
            except Exception:
                continue

        if not ro_results:
            return

        # Aggregate metrics
        total_revenue = sum(r.total_revenue for r in ro_results)
        total_cost = sum(r.total_cost for r in ro_results)
        total_gp = sum(r.gp_dollars for r in ro_results)
        gp_pct = (total_gp / total_revenue * 100) if total_revenue > 0 else 0

        await websocket.send_json({
            "type": "initial_data",
            "data": {
                "date": today,
                "sales": cents_to_dollars(total_revenue),
                "cost": cents_to_dollars(total_cost),
                "gross_profit": cents_to_dollars(total_gp),
                "gp_percentage": round(gp_pct, 2),
                "car_count": len(ro_results),
                "aro": cents_to_dollars(int(total_revenue / len(ro_results))),
                "updated_at": datetime.now().isoformat()
            }
        })

    except Exception as e:
        print(f"[WS] Error sending initial data: {e}")


async def _broadcast_dashboard_update():
    """Fetch current data and broadcast to all dashboard subscribers."""
    manager = get_ws_manager()

    try:
        client = await get_tm_client()
        today = date.today().isoformat()

        # Get today's ROs
        ros = await client.get_ros_for_period(
            start_date=today,
            end_date=today,
            status_filter=[2, 5, 6]  # WIP, POSTED, COMPLETED
        )

        if not ros:
            await manager.send_dashboard_update({
                "message": "No ROs found",
                "date": today,
                "car_count": 0
            })
            return

        # Calculate GP
        ro_results = []
        for ro in ros:
            try:
                result = await calculate_ro_true_gp(ro, client)
                ro_results.append(result)
            except Exception:
                continue

        if not ro_results:
            return

        # Aggregate
        total_revenue = sum(r.total_revenue for r in ro_results)
        total_cost = sum(r.total_cost for r in ro_results)
        total_gp = sum(r.gp_dollars for r in ro_results)
        gp_pct = (total_gp / total_revenue * 100) if total_revenue > 0 else 0

        # Broadcast dashboard update
        await manager.send_dashboard_update({
            "date": today,
            "sales": cents_to_dollars(total_revenue),
            "cost": cents_to_dollars(total_cost),
            "gross_profit": cents_to_dollars(total_gp),
            "gp_percentage": round(gp_pct, 2),
            "car_count": len(ro_results),
            "aro": cents_to_dollars(int(total_revenue / len(ro_results))),
            "updated_at": datetime.now().isoformat()
        })

        # Also broadcast tech update
        tech_performance = aggregate_tech_performance(ro_results)
        tech_data = [
            {
                "tech_id": tp.tech_id,
                "tech_name": tp.tech_name,
                "hours_billed": round(tp.hours_billed, 2),
                "labor_profit": cents_to_dollars(tp.labor_profit),
                "gp_per_hour": cents_to_dollars(tp.gp_per_hour)
            }
            for tp in sorted(
                tech_performance.values(),
                key=lambda x: x.labor_profit,
                reverse=True
            )
        ]
        await manager.send_tech_update(tech_data)

        # Check for alerts
        if gp_pct < 45:
            await manager.send_alert({
                "message": f"GP% dropped to {gp_pct:.1f}% - below 45% threshold",
                "severity": "critical",
                "metric": "gp_percentage",
                "value": round(gp_pct, 2)
            })
        elif gp_pct < 50:
            await manager.send_alert({
                "message": f"GP% at {gp_pct:.1f}% - approaching 50% threshold",
                "severity": "warning",
                "metric": "gp_percentage",
                "value": round(gp_pct, 2)
            })

    except Exception as e:
        print(f"[Realtime] Broadcast error: {e}")


async def _auto_refresh_loop():
    """Background task for automatic dashboard refresh."""
    global _refresh_interval

    print(f"[Realtime] Auto-refresh started (interval: {_refresh_interval}s)")

    while True:
        try:
            await _broadcast_dashboard_update()
            await asyncio.sleep(_refresh_interval)
        except asyncio.CancelledError:
            print("[Realtime] Auto-refresh stopped")
            break
        except Exception as e:
            print(f"[Realtime] Auto-refresh error: {e}")
            await asyncio.sleep(10)  # Retry after error
