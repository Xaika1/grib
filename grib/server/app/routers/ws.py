from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.errors import GribError
from app.core.event_bus import Connection, bus
from app.db import SessionLocal
from app.repositories import UserRepo
from app.services import alert_service, auth_service, dashboard_service

router = APIRouter()


def _authenticate(token: str) -> tuple[int, set[int] | None]:
    with SessionLocal() as session:
        user = auth_service.user_from_token(session, token)
        projects = alert_service.alert_projects(session, user)
        return user.id, (set(projects) if projects is not None else None)


def _dashboard_collectors(user_id: int, dashboard_id: int) -> set[int]:
    with SessionLocal() as session:
        user = UserRepo(session).get_or_404(user_id)
        return dashboard_service.subscription_collectors(session, user, dashboard_id)


@router.websocket("/ws")
async def websocket(ws: WebSocket, token: str = ""):
    await ws.accept()
    try:
        user_id, alert_projects = await run_in_threadpool(_authenticate, token)
    except GribError as exc:
        await ws.send_json({"type": "error", "message": exc.message})
        await ws.close(code=4401)
        return

    conn = Connection(ws=ws, user_id=user_id, alert_projects=alert_projects)
    bus.add(conn)
    try:
        await ws.send_json({"type": "hello", "user_id": user_id})
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "subscribe":
                try:
                    dashboard_id = int(msg.get("dashboard_id"))
                    collectors = await run_in_threadpool(_dashboard_collectors, user_id, dashboard_id)
                except (GribError, TypeError, ValueError) as exc:
                    async with conn.send_lock:
                        await ws.send_json({"type": "error", "message": getattr(exc, "message", "Неверная подписка")})
                    continue
                bus.subscribe(conn, dashboard_id, collectors)
                async with conn.send_lock:
                    await ws.send_json({"type": "subscribed", "dashboard_id": dashboard_id, "collectors": sorted(collectors)})
            elif kind == "unsubscribe":
                bus.subscribe(conn, None, set())
            elif kind == "ping":
                async with conn.send_lock:
                    await ws.send_json({"type": "pong"})
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        bus.remove(conn)
