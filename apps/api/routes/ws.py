import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from apps.api.settings import Settings

router = APIRouter()
settings = Settings()


@router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe("jobbot:logs")
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                continue
            data = message.get("data")
            if isinstance(data, str):
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = {"message": data}
            else:
                payload = {"message": str(data)}
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("jobbot:logs")
        await pubsub.close()
        await redis.close()
