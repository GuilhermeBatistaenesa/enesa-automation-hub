from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import allowed_robot_ids_for_permission, require_permission
from app.core.rbac import (
    PERMISSION_ROBOT_RUN,
    PERMISSION_RUN_READ,
    PERMISSION_SERVICE_MANAGE,
    PERMISSION_SERVICE_READ,
    PERMISSION_SERVICE_RUN,
)
from app.db.session import get_db
from app.schemas.common import Message
from app.schemas.portal import (
    DomainCreate,
    DomainRead,
    DomainUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceRunRequest,
    ServiceUpdate,
)
from app.schemas.run import RunRead
from app.services.audit_service import extract_client_ip, log_audit_event
from app.services.identity_service import Principal
from app.services.portal_service import (
    create_domain,
    create_service,
    delete_domain,
    delete_service,
    execute_service,
    get_service,
    list_domains,
    list_runs_for_service,
    list_services,
    list_services_by_domain_slug,
    update_domain,
    update_service,
)

router = APIRouter(tags=["portal"])


def _deny_if_robot_out_of_scope(db: Session, principal: Principal, robot_id: UUID, permission: str) -> None:
    allowed_ids = allowed_robot_ids_for_permission(db=db, principal=principal, permission=permission)
    if allowed_ids is not None and robot_id not in allowed_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente para o robo vinculado ao servico.")


@router.post("/domains", response_model=DomainRead, status_code=status.HTTP_201_CREATED)
def create_domain_endpoint(
    payload: DomainCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> DomainRead:
    try:
        domain = create_domain(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="domain.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="domain",
        target_id=str(domain.id),
        metadata={"domain_id": str(domain.id), "name": domain.name, "slug": domain.slug},
    )
    return DomainRead.model_validate(domain)


@router.get("/domains", response_model=list[DomainRead])
def list_domains_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_SERVICE_READ)),
) -> list[DomainRead]:
    items, _ = list_domains(db=db, skip=skip, limit=limit)
    return [DomainRead.model_validate(item) for item in items]


@router.patch("/domains/{domain_id}", response_model=DomainRead)
def update_domain_endpoint(
    domain_id: UUID,
    payload: DomainUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> DomainRead:
    try:
        domain = update_domain(db=db, domain_id=domain_id, payload=payload)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="domain.updated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="domain",
        target_id=str(domain.id),
        metadata={"domain_id": str(domain.id)},
    )
    return DomainRead.model_validate(domain)


@router.delete("/domains/{domain_id}", response_model=Message)
def delete_domain_endpoint(
    domain_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> Message:
    try:
        delete_domain(db=db, domain_id=domain_id)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="domain.deleted",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="domain",
        target_id=str(domain_id),
        metadata={"domain_id": str(domain_id)},
    )
    return Message(message="Domain removed successfully.")


@router.get("/domains/{slug}/services", response_model=list[ServiceRead])
def list_services_by_slug_endpoint(
    slug: str,
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_SERVICE_READ)),
) -> list[ServiceRead]:
    try:
        _, services = list_services_by_domain_slug(db=db, slug=slug, enabled_only=not include_disabled)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [ServiceRead.model_validate(item) for item in services]


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service_endpoint(
    payload: ServiceCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> ServiceRead:
    try:
        service = create_service(db=db, payload=payload, created_by=principal.user.id if principal.user else None)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="service.created",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="service",
        target_id=str(service.id),
        metadata={"service_id": str(service.id), "domain_id": str(service.domain_id), "robot_id": str(service.robot_id)},
    )
    return ServiceRead.model_validate(service)


@router.get("/services", response_model=list[ServiceRead])
def list_services_endpoint(
    domain_id: UUID | None = Query(None),
    enabled_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_SERVICE_READ)),
) -> list[ServiceRead]:
    items, _ = list_services(db=db, skip=skip, limit=limit, domain_id=domain_id, enabled_only=True if enabled_only else None)
    return [ServiceRead.model_validate(item) for item in items]


@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service_endpoint(
    service_id: UUID,
    db: Session = Depends(get_db),
    _: Principal = Depends(require_permission(PERMISSION_SERVICE_READ)),
) -> ServiceRead:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    return ServiceRead.model_validate(service)


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service_endpoint(
    service_id: UUID,
    payload: ServiceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> ServiceRead:
    try:
        service = update_service(db=db, service_id=service_id, payload=payload)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="service.updated",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="service",
        target_id=str(service.id),
        metadata={"service_id": str(service.id)},
    )
    return ServiceRead.model_validate(service)


@router.delete("/services/{service_id}", response_model=Message)
def delete_service_endpoint(
    service_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_MANAGE)),
) -> Message:
    try:
        delete_service(db=db, service_id=service_id)
    except ValueError as exc:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in str(exc).lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="service.deleted",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="service",
        target_id=str(service_id),
        metadata={"service_id": str(service_id)},
    )
    return Message(message="Service removed successfully.")


@router.post("/services/{service_id}/run", response_model=RunRead, status_code=status.HTTP_202_ACCEPTED)
async def run_service_endpoint(
    service_id: UUID,
    payload: ServiceRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_SERVICE_RUN)),
) -> RunRead:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    _deny_if_robot_out_of_scope(db=db, principal=principal, robot_id=service.robot_id, permission=PERMISSION_ROBOT_RUN)

    try:
        result = await execute_service(
            db=db,
            service_id=service_id,
            triggered_by=principal.user.id if principal.user else None,
            parameters=payload.parameters,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    log_audit_event(
        db=db,
        action="service.run.triggered",
        principal=principal,
        actor_ip=extract_client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None),
        target_type="run",
        target_id=str(result.run.run_id),
        metadata={
            "run_id": str(result.run.run_id),
            "service_id": str(service_id),
            "robot_id": str(service.robot_id),
            "version_id": str(result.run.robot_version_id),
            "parameters": result.validated_parameters,
        },
    )
    return RunRead.model_validate(result.run)


@router.get("/services/{service_id}/runs", response_model=list[RunRead])
def list_service_runs_endpoint(
    service_id: UUID,
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    principal: Principal = Depends(require_permission(PERMISSION_RUN_READ)),
) -> list[RunRead]:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found.")
    _deny_if_robot_out_of_scope(db=db, principal=principal, robot_id=service.robot_id, permission=PERMISSION_RUN_READ)
    items = list_runs_for_service(db=db, service_id=service_id, limit=limit)
    return [RunRead.model_validate(item) for item in items]
