from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.robot import RobotCreate, RobotListResponse, RobotRead
from app.services.robot_service import create_robot, list_robots

router = APIRouter(prefix="/robots", tags=["robots"])


@router.post(
    "",
    response_model=RobotRead,
    dependencies=[Depends(require_permission("robots:create", "robots"))],
)
def register_robot(
    payload: RobotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("robots:create", "robots")),
) -> RobotRead:
    robot = create_robot(db=db, payload=payload, created_by=current_user.id)
    return RobotRead.model_validate(robot)


@router.get(
    "",
    response_model=RobotListResponse,
    dependencies=[Depends(require_permission("robots:read", "robots"))],
)
def get_robots(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> RobotListResponse:
    items, total = list_robots(db=db, skip=skip, limit=limit)
    return RobotListResponse(items=[RobotRead.model_validate(item) for item in items], total=total)

