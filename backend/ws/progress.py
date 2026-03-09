import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect


class ProgressManager:
    """Manages WebSocket connections for per-video progress updates."""

    def __init__(self):
        # video_id -> set of connected websockets
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, video_id: str, ws: WebSocket):
        await ws.accept()
        if video_id not in self._connections:
            self._connections[video_id] = set()
        self._connections[video_id].add(ws)

    def disconnect(self, video_id: str, ws: WebSocket):
        if video_id in self._connections:
            self._connections[video_id].discard(ws)
            if not self._connections[video_id]:
                del self._connections[video_id]

    async def broadcast(self, video_id: str, stage: str, percent: float, message: str):
        """Send progress update to all connected clients for a video."""
        if video_id not in self._connections:
            return

        data = json.dumps({
            "stage": stage,
            "percent": round(percent, 1),
            "message": message,
        })

        dead = set()
        for ws in self._connections[video_id]:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections[video_id].discard(ws)


# Singleton
progress_manager = ProgressManager()
