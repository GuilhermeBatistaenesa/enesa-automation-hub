from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_deploy_token
from app.db.session import get_db
from app.models.robot import ArtifactType
from app.schemas.robot import RobotVersionRead
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.robot_service import is_valid_semver, publish_robot_version
from app.services.storage_service import extract_required_env_keys_from_artifact, get_artifact_storage

router = APIRouter(prefix="/deploy", tags=["deploy"])


@router.post("/robots/{robot_id}/versions/publish", response_model=RobotVersionRead, status_code=status.HTTP_201_CREATED)
async def publish_version_from_ci(
    robot_id: UUID,
    request: Request,
    _: str = Depends(require_deploy_token),
    version: str = Form(...),
    changelog: str | None = Form(default=None),
    commit_sha: str = Form(...),
    branch: str = Form(...),
    build_url: str = Form(...),
    activate: bool = Form(default=True),
    channel: str = Form(default="stable"),
    artifact: UploadFile = File(...),
    entrypoint_path: str = Form(default="main.py"),
    entrypoint_type: str = Form(default="PYTHON"),
    arguments_json: str | None = Form(default=None),
    env_vars_json: str | None = Form(default=None),
    working_directory: str | None = Form(default=None),
    db: Session = Depends(get_db),
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
            created_by=None,
            activate=activate,
            created_source="github_actions",
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
        principal=None,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="robot_version",
        target_id=str(published.id),
        metadata={
            "source": "github_actions",
            "robot_id": str(robot_id),
            "version": version,
            "channel": channel,
            "commit_sha": commit_sha,
            "branch": branch,
            "build_url": build_url,
            "artifact_type": stored.artifact_type,
            "artifact_path": stored.relative_path,
            "artifact_sha256": stored.sha256,
            "activate": activate,
            "required_env_keys_json": required_env_keys,
        },
    )
    return RobotVersionRead.model_validate(published)
