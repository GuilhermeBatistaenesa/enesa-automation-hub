from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.portal import Domain, Service
from app.models.robot import Robot, RobotVersion
from app.models.run import Run
from app.schemas.portal import (
    DomainCreate,
    DomainUpdate,
    RunTemplateSchema,
    ServiceCreate,
    ServiceFormSchema,
    ServiceUpdate,
    ValidatedServiceParameters,
    coerce_field_value,
)
from app.schemas.run import RunExecuteRequest
from app.services.run_service import create_run_and_enqueue, list_runs

slug_pattern = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(slots=True)
class ServiceExecutionResult:
    run: Run
    validated_parameters: dict[str, Any]


def _domain_query() -> Select[tuple[Domain]]:
    return select(Domain).order_by(Domain.name.asc())


def _service_query() -> Select[tuple[Service]]:
    return select(Service).options(joinedload(Service.domain), joinedload(Service.default_version)).order_by(Service.created_at.desc())


def validate_form_schema(raw_schema: dict[str, Any]) -> ServiceFormSchema:
    try:
        return ServiceFormSchema.model_validate(raw_schema or {})
    except ValidationError as exc:
        raise ValueError(f"Invalid form_schema_json: {exc}") from exc


def validate_run_template(raw_template: dict[str, Any]) -> RunTemplateSchema:
    try:
        return RunTemplateSchema.model_validate(raw_template or {})
    except ValidationError as exc:
        raise ValueError(f"Invalid run_template_json: {exc}") from exc


def validate_service_parameters(
    form_schema: ServiceFormSchema,
    run_template: RunTemplateSchema,
    parameters: dict[str, Any],
) -> ValidatedServiceParameters:
    parameter_keys = {field.key for field in form_schema.fields}
    unknown = sorted(set(parameters.keys()) - parameter_keys)
    if unknown:
        raise ValueError(f"Unknown parameters: {', '.join(unknown)}.")

    resolved: dict[str, Any] = {}
    for field in form_schema.fields:
        value = parameters.get(field.key, run_template.defaults.get(field.key, field.default))
        if value is None:
            if field.required:
                raise ValueError(f"Field '{field.label}' is required.")
            continue
        if field.required and isinstance(value, str) and not value.strip():
            raise ValueError(f"Field '{field.label}' is required.")

        coerced = coerce_field_value(field, value)
        _validate_business_rules(field, coerced)
        resolved[field.key] = coerced

    runtime_arguments: list[str] = []
    runtime_env: dict[str, str] = {}

    aliased_values = {
        run_template.mapping.parameter_aliases.get(key, key): value
        for key, value in resolved.items()
    }
    format_context = {
        **{key: _stringify(value) for key, value in resolved.items()},
        **{key: _stringify(value) for key, value in aliased_values.items()},
    }

    for template in run_template.mapping.runtime_arguments:
        runtime_arguments.append(_render_template(template, format_context))

    for env_key, env_template in run_template.mapping.runtime_env.items():
        runtime_env[env_key] = _render_template(env_template, format_context)

    return ValidatedServiceParameters(
        resolved_parameters=resolved,
        runtime_arguments=runtime_arguments,
        runtime_env=runtime_env,
    )


def create_domain(db: Session, payload: DomainCreate) -> Domain:
    _validate_slug(payload.slug)
    existing_name = db.scalar(select(Domain).where(Domain.name == payload.name))
    if existing_name:
        raise ValueError("Domain name already exists.")
    existing = db.scalar(select(Domain).where(Domain.slug == payload.slug))
    if existing:
        raise ValueError("Domain slug already exists.")

    domain = Domain(name=payload.name, slug=payload.slug, description=payload.description)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


def list_domains(db: Session, skip: int = 0, limit: int = 100) -> tuple[list[Domain], int]:
    total = db.scalar(select(func.count()).select_from(Domain)) or 0
    items = list(db.scalars(_domain_query().offset(skip).limit(limit)))
    return items, total


def get_domain_by_id(db: Session, domain_id: UUID) -> Domain | None:
    return db.scalar(select(Domain).where(Domain.id == domain_id))


def get_domain_by_slug(db: Session, slug: str) -> Domain | None:
    return db.scalar(select(Domain).where(Domain.slug == slug))


def update_domain(db: Session, domain_id: UUID, payload: DomainUpdate) -> Domain:
    domain = get_domain_by_id(db=db, domain_id=domain_id)
    if not domain:
        raise ValueError("Domain not found.")

    if "slug" in payload.model_fields_set:
        if payload.slug is None:
            raise ValueError("slug cannot be null.")
        _validate_slug(payload.slug)
        existing = db.scalar(select(Domain).where(Domain.slug == payload.slug, Domain.id != domain_id))
        if existing:
            raise ValueError("Domain slug already exists.")
        domain.slug = payload.slug

    if "name" in payload.model_fields_set:
        if payload.name is None:
            raise ValueError("name cannot be null.")
        existing_name = db.scalar(select(Domain).where(Domain.name == payload.name, Domain.id != domain_id))
        if existing_name:
            raise ValueError("Domain name already exists.")
        domain.name = payload.name
    if "description" in payload.model_fields_set:
        domain.description = payload.description

    db.commit()
    db.refresh(domain)
    return domain


def delete_domain(db: Session, domain_id: UUID) -> None:
    domain = get_domain_by_id(db=db, domain_id=domain_id)
    if not domain:
        raise ValueError("Domain not found.")
    linked_services = db.scalar(select(func.count()).select_from(Service).where(Service.domain_id == domain_id)) or 0
    if linked_services > 0:
        raise ValueError("Domain has linked services. Remove or move services before deleting the domain.")
    db.delete(domain)
    db.commit()


def create_service(db: Session, payload: ServiceCreate, created_by: UUID | None) -> Service:
    validate_form_schema(payload.form_schema_json)
    validate_run_template(payload.run_template_json)
    _validate_service_references(
        db=db,
        domain_id=payload.domain_id,
        robot_id=payload.robot_id,
        default_version_id=payload.default_version_id,
    )

    existing = db.scalar(
        select(Service).where(
            Service.domain_id == payload.domain_id,
            Service.title == payload.title,
        )
    )
    if existing:
        raise ValueError("Service title already exists in this domain.")

    service = Service(
        domain_id=payload.domain_id,
        robot_id=payload.robot_id,
        title=payload.title,
        description=payload.description,
        icon=payload.icon,
        enabled=payload.enabled,
        default_version_id=payload.default_version_id,
        form_schema_json=payload.form_schema_json,
        run_template_json=payload.run_template_json,
        created_by=created_by,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return get_service(db=db, service_id=service.id) or service


def list_services(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    domain_id: UUID | None = None,
    enabled_only: bool | None = None,
) -> tuple[list[Service], int]:
    stmt = _service_query()
    count_stmt = select(func.count()).select_from(Service)

    if domain_id:
        stmt = stmt.where(Service.domain_id == domain_id)
        count_stmt = count_stmt.where(Service.domain_id == domain_id)
    if enabled_only is True:
        stmt = stmt.where(Service.enabled.is_(True))
        count_stmt = count_stmt.where(Service.enabled.is_(True))

    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.offset(skip).limit(limit)))
    return items, total


def list_services_by_domain_slug(db: Session, slug: str, enabled_only: bool = True) -> tuple[Domain, list[Service]]:
    domain = get_domain_by_slug(db=db, slug=slug)
    if not domain:
        raise ValueError("Domain not found.")

    stmt = _service_query().where(Service.domain_id == domain.id)
    if enabled_only:
        stmt = stmt.where(Service.enabled.is_(True))
    services = list(db.scalars(stmt))
    return domain, services


def get_service(db: Session, service_id: UUID) -> Service | None:
    return db.scalar(_service_query().where(Service.id == service_id))


def update_service(db: Session, service_id: UUID, payload: ServiceUpdate) -> Service:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise ValueError("Service not found.")

    target_domain_id = payload.domain_id if "domain_id" in payload.model_fields_set and payload.domain_id else service.domain_id
    target_robot_id = payload.robot_id if "robot_id" in payload.model_fields_set and payload.robot_id else service.robot_id
    default_version_explicit = "default_version_id" in payload.model_fields_set
    target_default_version_id = payload.default_version_id if default_version_explicit else service.default_version_id
    _validate_service_references(
        db=db,
        domain_id=target_domain_id,
        robot_id=target_robot_id,
        default_version_id=target_default_version_id,
    )

    if payload.form_schema_json is not None:
        validate_form_schema(payload.form_schema_json)
        service.form_schema_json = payload.form_schema_json
    if payload.run_template_json is not None:
        validate_run_template(payload.run_template_json)
        service.run_template_json = payload.run_template_json
    if "domain_id" in payload.model_fields_set:
        if payload.domain_id is None:
            raise ValueError("domain_id cannot be null.")
        service.domain_id = payload.domain_id
    if "robot_id" in payload.model_fields_set:
        if payload.robot_id is None:
            raise ValueError("robot_id cannot be null.")
        service.robot_id = payload.robot_id
    if "title" in payload.model_fields_set:
        if payload.title is None:
            raise ValueError("title cannot be null.")
        duplicate = db.scalar(
            select(Service).where(
                Service.domain_id == target_domain_id,
                Service.title == payload.title,
                Service.id != service_id,
            )
        )
        if duplicate:
            raise ValueError("Service title already exists in this domain.")
        service.title = payload.title
    if "description" in payload.model_fields_set:
        service.description = payload.description
    if "icon" in payload.model_fields_set:
        service.icon = payload.icon
    if "enabled" in payload.model_fields_set:
        if payload.enabled is None:
            raise ValueError("enabled cannot be null.")
        service.enabled = payload.enabled
    if default_version_explicit:
        service.default_version_id = payload.default_version_id

    db.commit()
    db.refresh(service)
    return get_service(db=db, service_id=service.id) or service


def delete_service(db: Session, service_id: UUID) -> None:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise ValueError("Service not found.")
    linked_runs = db.scalar(select(func.count()).select_from(Run).where(Run.service_id == service_id)) or 0
    if linked_runs > 0:
        raise ValueError("Service has historical runs and cannot be deleted. Disable it instead.")
    db.delete(service)
    db.commit()


async def execute_service(
    db: Session,
    service_id: UUID,
    triggered_by: UUID | None,
    parameters: dict[str, Any],
) -> ServiceExecutionResult:
    service = get_service(db=db, service_id=service_id)
    if not service:
        raise ValueError("Service not found.")
    if not service.enabled:
        raise ValueError("Service is currently disabled.")

    form_schema = validate_form_schema(service.form_schema_json)
    run_template = validate_run_template(service.run_template_json)
    validated = validate_service_parameters(form_schema=form_schema, run_template=run_template, parameters=parameters)
    env_name = str(run_template.defaults.get("env_name", "PROD")).upper()

    payload = RunExecuteRequest(
        version_id=service.default_version_id,
        runtime_arguments=validated.runtime_arguments,
        runtime_env=validated.runtime_env,
        env_name=env_name,
    )
    run = await create_run_and_enqueue(
        db=db,
        robot_id=service.robot_id,
        payload=payload,
        triggered_by=triggered_by,
        service_id=service.id,
        parameters_json=validated.resolved_parameters,
    )
    return ServiceExecutionResult(run=run, validated_parameters=validated.resolved_parameters)


def list_runs_for_service(db: Session, service_id: UUID, limit: int = 20) -> list[Run]:
    items, _ = list_runs(db=db, service_id=service_id, skip=0, limit=limit)
    return items


def _validate_service_references(
    db: Session,
    domain_id: UUID,
    robot_id: UUID,
    default_version_id: UUID | None,
) -> None:
    domain_exists = db.scalar(select(func.count()).select_from(Domain).where(Domain.id == domain_id))
    if not domain_exists:
        raise ValueError("Domain not found.")
    robot_exists = db.scalar(select(func.count()).select_from(Robot).where(Robot.id == robot_id))
    if not robot_exists:
        raise ValueError("Robot not found.")
    if default_version_id is not None:
        version = db.scalar(select(RobotVersion).where(RobotVersion.id == default_version_id))
        if not version or version.robot_id != robot_id:
            raise ValueError("default_version_id must belong to the selected robot.")


def _validate_slug(slug: str) -> None:
    if not slug_pattern.fullmatch(slug):
        raise ValueError("Invalid slug format. Use lowercase and hyphen, example: dp-rh.")


def _validate_business_rules(field, value: Any) -> None:
    rules = field.validation
    if not rules:
        return

    if isinstance(value, str):
        if rules.min is not None and len(value) < rules.min:
            raise ValueError(f"Field '{field.label}' must contain at least {int(rules.min)} characters.")
        if rules.max is not None and len(value) > rules.max:
            raise ValueError(f"Field '{field.label}' must contain at most {int(rules.max)} characters.")
        if rules.regex and not re.fullmatch(rules.regex, value):
            raise ValueError(f"Field '{field.label}' has invalid format.")
    elif isinstance(value, (int, float)):
        if rules.min is not None and value < rules.min:
            raise ValueError(f"Field '{field.label}' must be >= {rules.min}.")
        if rules.max is not None and value > rules.max:
            raise ValueError(f"Field '{field.label}' must be <= {rules.max}.")


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


class _StrictFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:  # pragma: no cover - handled by exception path
        raise KeyError(key)


def _render_template(template: str, context: dict[str, str]) -> str:
    try:
        return template.format_map(_StrictFormatDict(context))
    except KeyError as exc:
        raise ValueError(f"run_template_json references unknown field '{exc.args[0]}'.") from exc
