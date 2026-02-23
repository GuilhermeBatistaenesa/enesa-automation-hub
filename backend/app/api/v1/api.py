from fastapi import APIRouter

from app.api.v1.endpoints import alerts, auth, deploy, health, ops, portal, robots, runs, users, workers, ws_logs

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(robots.router)
api_router.include_router(runs.router)
api_router.include_router(portal.router)
api_router.include_router(alerts.router)
api_router.include_router(deploy.router)
api_router.include_router(workers.router)
api_router.include_router(ops.router)
api_router.include_router(users.router)
api_router.include_router(ws_logs.router)
