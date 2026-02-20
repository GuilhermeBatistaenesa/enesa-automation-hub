from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, robots, runs, ws_logs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(robots.router)
api_router.include_router(runs.router)
api_router.include_router(ws_logs.router)

