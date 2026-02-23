from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.rbac import PERMISSION_WORKER_MANAGE
from app.db.session import get_db
from app.schemas.worker import OpsStatusRead
from app.services.identity_service import Principal
from app.services.worker_service import get_ops_status

router = APIRouter(prefix="/ops", tags=["operations"])
_started_at_monotonic = time.monotonic()


@router.get("/status", response_model=OpsStatusRead)
def get_operations_status(
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_WORKER_MANAGE)),
) -> OpsStatusRead:
    data = get_ops_status(db=db, started_at_monotonic=_started_at_monotonic)
    return OpsStatusRead.model_validate(data)
