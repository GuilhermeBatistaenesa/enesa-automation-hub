from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import allowed_robot_ids_for_permission, require_permission
from app.core.rbac import PERMISSION_ROBOT_PUBLISH, PERMISSION_ROBOT_READ
from app.db.session import get_db
from app.models.robot import ArtifactType
from app.schemas.common import Message
from app.schemas.env_var import RobotEnvVarRead, RobotEnvVarUpsertRequest
from app.schemas.robot import RobotCreate, RobotListResponse, RobotRead, RobotTagsUpdate, RobotVersionRead
from app.schemas.scheduler import ScheduleCreate, ScheduleRead, ScheduleUpdate, SlaRuleCreate, SlaRuleRead, SlaRuleUpdate
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.robot_service import (
    activate_robot_version,
    create_robot,
    get_robot,
    is_valid_semver,
    list_robot_versions,
    list_robots,
    list_robots_scoped,
    publish_robot_version,
    update_robot_tags,
)
from app.services.robot_env_service import delete_env_var, list_env_vars, normalize_env_name, upsert_env_vars
from app.services.scheduler_service import create_schedule, create_sla_rule, delete_schedule, get_schedule, get_sla_rule, update_schedule, update_sla_rule
from app.services.storage_service import extract_required_env_keys_from_artifact, get_artifact_storage

router = APIRouter(prefix="/robots", tags=["robots"])


def _serialize_version(version) -> RobotVersionRead:
    return RobotVersionRead.model_validate(version)


def _serialize_robot(robot) -> RobotRead:
    versions = sorted(getattr(robot, "versions", []), key=lambda item: item.created_at, reverse=True)
    return RobotRead.model_validate(
        {
            "id": robot.id,
            "name": robot.name,
            "description": robot.description,
            "created_at": robot.created_at,
            "updated_at": robot.updated_at,
            "versions": [_serialize_version(version) for version in versions],
            "tags": [item.tag for item in getattr(robot, "tags", [])],
        }
    )


@router.post("", response_model=RobotRead)
def register_robot(
    payload: RobotCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH)),
) -> RobotRead:
    robot = create_robot(db=db, payload=payload, created_by=principal.user.id if principal.user else None)
    log_audit_event(
        db=db,
        action="robot.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot",
        target_id=str(robot.id),
        metadata={"robot_id": str(robot.id), "name": robot.name, "tags": payload.tags},
    )
    return _serialize_robot(robot)


@router.get("", response_model=RobotListResponse)
def get_robots(
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_READ)),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> RobotListResponse:
    allowed_ids = allowed_robot_ids_for_permission(db=db, principal=principal, permission=PERMISSION_ROBOT_READ)
    if allowed_ids is None:
        items, total = list_robots(db=db, skip=skip, limit=limit)
    else:
        items, total = list_robots_scoped(db=db, robot_ids=allowed_ids, skip=skip, limit=limit)
    return RobotListResponse(items=[_serialize_robot(item) for item in items], total=total)


@router.get("/{robot_id}/versions", response_model=list[RobotVersionRead])
def get_robot_versions(
    robot_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ROBOT_READ, robot_id_param="robot_id")),
) -> list[RobotVersionRead]:
    robot = get_robot(db=db, robot_id=robot_id)
    if not robot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found.")
    return [_serialize_version(version) for version in list_robot_versions(db=db, robot_id=robot_id)]


@router.post("/{robot_id}/versions/publish", response_model=RobotVersionRead, status_code=status.HTTP_201_CREATED)
async def publish_version(
    robot_id: UUID,
    request: Request,
    version: str = Form(...),
    channel: str = Form(...),
    changelog: str | None = Form(default=None),
    artifact: UploadFile = File(...),
    entrypoint_path: str = Form(default="main.py"),
    entrypoint_type: str = Form(default="PYTHON"),
    arguments_json: str | None = Form(default=None),
    env_vars_json: str | None = Form(default=None),
    working_directory: str | None = Form(default=None),
    activate: bool = Form(default=True),
    commit_sha: str | None = Form(default=None),
    branch: str | None = Form(default=None),
    build_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> RobotVersionRead:
    if not is_valid_semver(version):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid semver version.")
    if channel not in {"stable", "beta", "hotfix"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid release channel.")

    try:
        parsed_arguments = json.loads(arguments_json) if arguments_json else []
        parsed_env_vars = json.loads(env_vars_json) if env_vars_json else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid arguments_json/env_vars_json payload.") from exc

    if not isinstance(parsed_arguments, list) or not all(isinstance(item, str) for item in parsed_arguments):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="arguments_json must be a JSON array of strings.")
    if not isinstance(parsed_env_vars, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in parsed_env_vars.items()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="env_vars_json must be a JSON object of string pairs.")

    storage = get_artifact_storage()
    try:
        stored = await storage.save_robot_version_artifact(robot_id=robot_id, version=version, upload=artifact)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    required_env_keys = extract_required_env_keys_from_artifact(
        artifact_path=stored.absolute_path,
        artifact_type=stored.artifact_type,
    )

    try:
        published = publish_robot_version(
            db=db,
            robot_id=robot_id,
            version=version,
            channel=channel,
            changelog=changelog,
            artifact_type=stored.artifact_type,
            artifact_path=stored.relative_path,
            artifact_sha256=stored.sha256,
            created_by=principal.user.id if principal.user else None,
            activate=activate,
            created_source="user",
            commit_sha=commit_sha,
            branch=branch,
            build_url=build_url,
            required_env_keys_json=required_env_keys,
            entrypoint_path=entrypoint_path,
            entrypoint_type=("EXE" if stored.artifact_type == ArtifactType.EXE.value else entrypoint_type),
            arguments=parsed_arguments,
            env_vars=parsed_env_vars,
            working_directory=working_directory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="robot_version_published",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot_version",
        target_id=str(published.id),
        metadata={
            "robot_id": str(robot_id),
            "version": version,
            "channel": channel,
            "artifact_type": stored.artifact_type,
            "artifact_path": stored.relative_path,
            "artifact_sha256": stored.sha256,
            "activate": activate,
            "commit_sha": commit_sha,
            "branch": branch,
            "build_url": build_url,
            "required_env_keys_json": required_env_keys,
        },
    )
    return _serialize_version(published)


@router.post("/{robot_id}/versions/{version_id}/activate", response_model=RobotVersionRead)
def activate_version(
    robot_id: UUID,
    version_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> RobotVersionRead:
    try:
        activated = activate_robot_version(db=db, robot_id=robot_id, version_id=version_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="robot_version_activated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot_version",
        target_id=str(version_id),
        metadata={"robot_id": str(robot_id), "version_id": str(version_id), "version": activated.version},
    )
    return _serialize_version(activated)


@router.patch("/{robot_id}/tags", response_model=RobotRead)
def patch_robot_tags(
    robot_id: UUID,
    payload: RobotTagsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> RobotRead:
    robot = update_robot_tags(db=db, robot_id=robot_id, tags=payload.tags)
    if not robot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Robot not found.")

    log_audit_event(
        db=db,
        action="robot_updated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot",
        target_id=str(robot_id),
        metadata={"robot_id": str(robot_id), "tags": payload.tags},
    )
    return _serialize_robot(robot)


@router.get("/{robot_id}/env", response_model=list[RobotEnvVarRead])
def get_robot_env_vars(
    robot_id: UUID,
    env: str = Query("PROD"),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ROBOT_READ, robot_id_param="robot_id")),
) -> list[RobotEnvVarRead]:
    try:
        return list_env_vars(db=db, robot_id=robot_id, env_name=env)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.put("/{robot_id}/env", response_model=list[RobotEnvVarRead])
def put_robot_env_vars(
    robot_id: UUID,
    payload: RobotEnvVarUpsertRequest,
    request: Request,
    env: str = Query("PROD"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> list[RobotEnvVarRead]:
    try:
        touched, actions = upsert_env_vars(
            db=db,
            robot_id=robot_id,
            env_name=env,
            items=payload.items,
            actor_user_id=principal.user.id if principal.user else None,
        )
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    normalized_env = normalize_env_name(env)
    for item, action in zip(touched, actions):
        log_audit_event(
            db=db,
            action=f"robot_env_var.{action}",
            principal=principal,
            actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
            target_type="robot_env_var",
            target_id=f"{robot_id}:{normalized_env}:{item.key}",
            metadata={
                "robot_id": str(robot_id),
                "env_name": normalized_env,
                "key": item.key,
                "is_secret": item.is_secret,
                "action": action,
            },
        )
    return list_env_vars(db=db, robot_id=robot_id, env_name=normalized_env)


@router.delete("/{robot_id}/env/{key}", response_model=Message)
def remove_robot_env_var(
    robot_id: UUID,
    key: str,
    request: Request,
    env: str = Query("PROD"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> Message:
    try:
        normalized_env = normalize_env_name(env)
        delete_env_var(db=db, robot_id=robot_id, env_name=normalized_env, key=key)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="robot_env_var.deleted",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot_env_var",
        target_id=f"{robot_id}:{normalized_env}:{key}",
        metadata={
            "robot_id": str(robot_id),
            "env_name": normalized_env,
            "key": key,
        },
    )
    return Message(message="Env key removed successfully.")


@router.post("/{robot_id}/schedule", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_robot_schedule(
    robot_id: UUID,
    payload: ScheduleCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> ScheduleRead:
    try:
        schedule = create_schedule(db=db, robot_id=robot_id, payload=payload, created_by=principal.user.id if principal.user else None)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="schedule.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="schedule",
        target_id=str(schedule.id),
        metadata={"robot_id": str(robot_id), "schedule_id": str(schedule.id)},
    )
    return ScheduleRead.model_validate(schedule)


@router.get("/{robot_id}/schedule", response_model=ScheduleRead)
def get_robot_schedule(
    robot_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ROBOT_READ, robot_id_param="robot_id")),
) -> ScheduleRead:
    schedule = get_schedule(db=db, robot_id=robot_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")
    return ScheduleRead.model_validate(schedule)


@router.patch("/{robot_id}/schedule", response_model=ScheduleRead)
def patch_robot_schedule(
    robot_id: UUID,
    payload: ScheduleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> ScheduleRead:
    try:
        schedule = update_schedule(db=db, robot_id=robot_id, payload=payload)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="schedule.updated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="schedule",
        target_id=str(schedule.id),
        metadata={"robot_id": str(robot_id), "schedule_id": str(schedule.id)},
    )
    return ScheduleRead.model_validate(schedule)


@router.delete("/{robot_id}/schedule", response_model=Message)
def remove_robot_schedule(
    robot_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> Message:
    try:
        delete_schedule(db=db, robot_id=robot_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="schedule.deleted",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="schedule",
        target_id=str(robot_id),
        metadata={"robot_id": str(robot_id)},
    )
    return Message(message="Schedule removed successfully.")


@router.post("/{robot_id}/sla", response_model=SlaRuleRead, status_code=status.HTTP_201_CREATED)
def create_robot_sla(
    robot_id: UUID,
    payload: SlaRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> SlaRuleRead:
    try:
        rule = create_sla_rule(db=db, robot_id=robot_id, payload=payload, created_by=principal.user.id if principal.user else None)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="sla.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="sla_rule",
        target_id=str(rule.id),
        metadata={"robot_id": str(robot_id), "sla_id": str(rule.id)},
    )
    return SlaRuleRead.model_validate(rule)


@router.get("/{robot_id}/sla", response_model=SlaRuleRead)
def get_robot_sla(
    robot_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_ROBOT_READ, robot_id_param="robot_id")),
) -> SlaRuleRead:
    rule = get_sla_rule(db=db, robot_id=robot_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA rule not found.")
    return SlaRuleRead.model_validate(rule)


@router.patch("/{robot_id}/sla", response_model=SlaRuleRead)
def patch_robot_sla(
    robot_id: UUID,
    payload: SlaRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_ROBOT_PUBLISH, robot_id_param="robot_id")),
) -> SlaRuleRead:
    try:
        rule = update_sla_rule(db=db, robot_id=robot_id, payload=payload)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="sla.updated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="sla_rule",
        target_id=str(rule.id),
        metadata={"robot_id": str(robot_id), "sla_id": str(rule.id)},
    )
    return SlaRuleRead.model_validate(rule)
