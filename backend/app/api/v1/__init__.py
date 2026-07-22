from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.endpoints.candidate import router as candidate_router
from app.api.v1.endpoints.jd import router as jd_router
from app.api.v1.endpoints.match import router as match_router
from app.api.v1.endpoints.resume import router as resume_router

api_v1_router = APIRouter()
api_v1_router.include_router(jd_router)
api_v1_router.include_router(resume_router)
api_v1_router.include_router(candidate_router)
api_v1_router.include_router(match_router)
api_v1_router.include_router(agent_router)
