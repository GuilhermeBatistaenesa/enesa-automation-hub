from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.robot import Robot
from app.models.robot_env_var import RobotEnvVar
from app.schemas.env_var import RobotEnvVarRead, RobotEnvVarUpsertItem
from app.services.encryption_service import decrypt_value, encrypt_value

ALLOWED_ENV_NAMES = {"PROD", "HML", "TEST"}


def normalize_env_name(env_name: str) -> str:
    normalized = (env_name or "").strip().upper()
    if normalized not in ALLOWED_ENV_NAMES:
        raise ValueError("env must be one of: PROD, HML, TEST.")
    return normalized


def _ensure_robot_exists(db: Session, robot_id: UUID) -> None:
    exists = db.scalar(select(Robot.id).where(Robot.id == robot_id))
    if not exists:
        raise ValueError("Robot not found.")


def list_env_vars(db: Session, robot_id: UUID, env_name: str) -> list[RobotEnvVarRead]:
    env_name = normalize_env_name(env_name)
    _ensure_robot_exists(db=db, robot_id=robot_id)
    items = list(
        db.scalars(
            select(RobotEnvVar)
            .where(RobotEnvVar.robot_id == robot_id, RobotEnvVar.env_name == env_name)
            .order_by(RobotEnvVar.key.asc())
        )
    )
    output: list[RobotEnvVarRead] = []
    for item in items:
        value = None
        if not item.is_secret:
            value = decrypt_value(item.value_encrypted)
        output.append(
            RobotEnvVarRead(
                robot_id=item.robot_id,
                env_name=item.env_name,
                key=item.key,
                is_secret=item.is_secret,
                is_set=bool(item.value_encrypted),
                value=value,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
        )
    return output


def upsert_env_vars(
    db: Session,
    robot_id: UUID,
    env_name: str,
    items: list[RobotEnvVarUpsertItem],
    actor_user_id: UUID | None,
) -> tuple[list[RobotEnvVar], list[str]]:
    env_name = normalize_env_name(env_name)
    _ensure_robot_exists(db=db, robot_id=robot_id)
    now = datetime.now(timezone.utc)

    touched: list[RobotEnvVar] = []
    actions: list[str] = []
    for payload in items:
        existing = db.scalar(
            select(RobotEnvVar).where(
                RobotEnvVar.robot_id == robot_id,
                RobotEnvVar.env_name == env_name,
                RobotEnvVar.key == payload.key,
            )
        )
        if payload.value is None:
            raise ValueError(f"value is required for key '{payload.key}'.")

        encrypted = encrypt_value(payload.value)
        if existing:
            existing.value_encrypted = encrypted
            existing.is_secret = payload.is_secret
            existing.updated_at = now
            existing.updated_by = actor_user_id
            touched.append(existing)
            actions.append("updated")
        else:
            created = RobotEnvVar(
                robot_id=robot_id,
                env_name=env_name,
                key=payload.key,
                value_encrypted=encrypted,
                is_secret=payload.is_secret,
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            db.add(created)
            touched.append(created)
            actions.append("created")

    db.commit()
    for item in touched:
        db.refresh(item)
    return touched, actions


def delete_env_var(db: Session, robot_id: UUID, env_name: str, key: str) -> None:
    env_name = normalize_env_name(env_name)
    _ensure_robot_exists(db=db, robot_id=robot_id)
    existing = db.scalar(
        select(RobotEnvVar).where(
            RobotEnvVar.robot_id == robot_id,
            RobotEnvVar.env_name == env_name,
            RobotEnvVar.key == key,
        )
    )
    if not existing:
        raise ValueError("Env key not found.")
    db.delete(existing)
    db.commit()


def resolve_runtime_env(db: Session, robot_id: UUID, env_name: str) -> dict[str, str]:
    env_name = normalize_env_name(env_name)
    items = list(
        db.scalars(
            select(RobotEnvVar).where(
                RobotEnvVar.robot_id == robot_id,
                RobotEnvVar.env_name == env_name,
            )
        )
    )
    output: dict[str, str] = {}
    for item in items:
        output[item.key] = decrypt_value(item.value_encrypted)
    return output


def list_defined_env_keys(db: Session, robot_id: UUID, env_name: str) -> set[str]:
    env_name = normalize_env_name(env_name)
    keys = db.scalars(
        select(RobotEnvVar.key).where(
            RobotEnvVar.robot_id == robot_id,
            RobotEnvVar.env_name == env_name,
        )
    )
    return set(keys)
