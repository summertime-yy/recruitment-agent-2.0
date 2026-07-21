from fastapi import Request
from redis import asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()


def get_redis(request: Request) -> aioredis.Redis:
    """FastAPI 依赖注入函数，从 app.state 取 Redis 客户端（PR-13 重构）。

    客户端生命周期由 ``app.main`` 的 lifespan 管理（创建 + aclose），
    新代码一律通过 ``Depends(get_redis)`` 获取，禁止 import 全局单例。
    """
    return request.app.state.redis
