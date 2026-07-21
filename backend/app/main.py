from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import asyncio as aioredis

from app.agent.skill_registry import get_skill_registry
from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.minio import ensure_buckets
from app.core.time import utcnow_naive
from app.models import Skill

settings = get_settings()


async def _sync_skills_to_db() -> None:
    import logging

    logger = logging.getLogger(__name__)
    registry = get_skill_registry()
    async with async_session_factory() as session:
        for skill_meta in registry.list_skills():
            from sqlalchemy import select

            result = await session.execute(select(Skill).where(Skill.skill_id == skill_meta["skill_id"]))
            existing = result.scalar_one_or_none()
            if existing:
                existing.current_version = skill_meta["version"]
                existing.skill_name = skill_meta["skill_name"]
                existing.description = skill_meta["description"]
                existing.updated_at = utcnow_naive()
                logger.info(f"Updated skill in DB: {skill_meta['skill_id']} v{skill_meta['version']}")
            else:
                skill = Skill(
                    skill_id=skill_meta["skill_id"],
                    skill_name=skill_meta["skill_name"],
                    description=skill_meta["description"],
                    current_version=skill_meta["version"],
                    status="ACTIVE",
                    created_at=utcnow_naive(),
                    updated_at=utcnow_naive(),
                )
                session.add(skill)
                logger.info(f"Registered skill in DB: {skill_meta['skill_id']} v{skill_meta['version']}")
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    logger = logging.getLogger(__name__)
    # Redis 客户端（PR-13）：挂到 app.state，shutdown 时 aclose
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        ensure_buckets(["resumes", "avatars", "exports"])
    except Exception as e:
        logger.warning(f"MinIO bucket initialization skipped: {e}")
    try:
        await _sync_skills_to_db()
    except Exception as e:
        logger.warning(f"Skill sync to DB skipped: {e}")
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get(f"{settings.API_V1_PREFIX}/health")
async def api_health_check():
    return {"status": "ok"}
