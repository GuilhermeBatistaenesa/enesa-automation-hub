from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.services.identity_service import Principal


def extract_client_ip(x_forwarded_for: str | None, fallback: str | None) -> str | None:
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return fallback


def log_audit_event(
    db: Session,
    action: str,
    principal: Principal | None,
    actor_ip: str | None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    actor_user_id = principal.user.id if principal and principal.user else None
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=metadata or {},
            ip=actor_ip,
        )
    )
    db.commit()

