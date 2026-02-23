from __future__ import annotations

import json
from typing import Any

from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from app.core.config import get_settings
from app.core.metrics import queue_depth

settings = get_settings()

_async_redis: AsyncRedis | None = None
_sync_redis: Redis | None = None


def get_run_log_channel(run_id: str) -> str:
    return settings.run_channel(run_id)


async def get_async_redis() -> AsyncRedis:
    global _async_redis
    if _async_redis is None:
        _async_redis = AsyncRedis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _async_redis


def get_sync_redis() -> Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = Redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _sync_redis


async def enqueue_run(payload: dict[str, Any]) -> None:
    redis = await get_async_redis()
    await redis.lpush(settings.redis_queue_name, json.dumps(payload))
    depth = await redis.llen(settings.redis_queue_name)
    queue_depth.set(depth)


async def publish_run_log(run_id: str, payload: dict[str, Any]) -> None:
    redis = await get_async_redis()
    await redis.publish(get_run_log_channel(run_id), json.dumps(payload, default=str))


def refresh_queue_depth_sync() -> int:
    redis = get_sync_redis()
    depth = redis.llen(settings.redis_queue_name)
    queue_depth.set(depth)
    return int(depth)
