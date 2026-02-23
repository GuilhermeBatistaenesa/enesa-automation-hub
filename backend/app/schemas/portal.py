from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

FIELD_TYPE_VALUES = {"text", "number", "date", "select", "checkbox"}


class FormFieldValidation(BaseModel):
    min: float | None = None
    max: float | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "FormFieldValidation":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("validation.min cannot be greater than validation.max.")
        return self


class FormFieldOption(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    value: str = Field(..., min_length=1, max_length=120)


class FormFieldSchema(BaseModel):
    key: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=120)
    type: Literal["text", "number", "date", "select", "checkbox"]
    required: bool = False
    default: Any | None = None
    helpText: str | None = Field(default=None, max_length=500)
    validation: FormFieldValidation | None = None
    options: list[FormFieldOption] | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "FormFieldSchema":
        if self.type == "select":
            if not self.options:
                raise ValueError(f"Field '{self.key}' of type 'select' requires non-empty options.")
        elif self.options:
            raise ValueError(f"Field '{self.key}' only supports options when type is 'select'.")
        return self


class ServiceFormSchema(BaseModel):
    fields: list[FormFieldSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ServiceFormSchema":
        seen: set[str] = set()
        for field in self.fields:
            if field.key in seen:
                raise ValueError(f"Duplicate field key '{field.key}' in form schema.")
            seen.add(field.key)
        return self


class RunTemplateMapping(BaseModel):
    runtime_arguments: list[str] = Field(default_factory=list)
    runtime_env: dict[str, str] = Field(default_factory=dict)
    parameter_aliases: dict[str, str] = Field(default_factory=dict)


class RunTemplateSchema(BaseModel):
    defaults: dict[str, Any] = Field(default_factory=dict)
    mapping: RunTemplateMapping = Field(default_factory=RunTemplateMapping)


class DomainCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    slug: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None


class DomainUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None


class DomainRead(ORMModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    created_at: datetime


class ServiceCreate(BaseModel):
    domain_id: UUID
    robot_id: UUID
    title: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=120)
    enabled: bool = True
    default_version_id: UUID | None = None
    form_schema_json: dict[str, Any]
    run_template_json: dict[str, Any] = Field(default_factory=dict)


class ServiceUpdate(BaseModel):
    domain_id: UUID | None = None
    robot_id: UUID | None = None
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    icon: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    default_version_id: UUID | None = None
    form_schema_json: dict[str, Any] | None = None
    run_template_json: dict[str, Any] | None = None


class ServiceRead(ORMModel):
    id: UUID
    domain_id: UUID
    robot_id: UUID
    title: str
    description: str | None
    icon: str | None
    enabled: bool
    default_version_id: UUID | None
    form_schema_json: dict[str, Any]
    run_template_json: dict[str, Any]
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class ServiceRunRequest(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class ValidatedServiceParameters(BaseModel):
    resolved_parameters: dict[str, Any]
    runtime_arguments: list[str]
    runtime_env: dict[str, str]


def coerce_field_value(field: FormFieldSchema, raw: Any) -> Any:
    if raw is None:
        return None

    if field.type == "text":
        if not isinstance(raw, str):
            raise ValueError(f"Field '{field.key}' must be text.")
        return raw

    if field.type == "number":
        if isinstance(raw, bool):
            raise ValueError(f"Field '{field.key}' must be a number.")
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            try:
                return float(raw)
            except ValueError as exc:
                raise ValueError(f"Field '{field.key}' must be a number.") from exc
        raise ValueError(f"Field '{field.key}' must be a number.")

    if field.type == "date":
        if isinstance(raw, date):
            return raw.isoformat()
        if isinstance(raw, str):
            try:
                parsed = date.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(f"Field '{field.key}' must be a date in format YYYY-MM-DD.") from exc
            return parsed.isoformat()
        raise ValueError(f"Field '{field.key}' must be a date in format YYYY-MM-DD.")

    if field.type == "checkbox":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        raise ValueError(f"Field '{field.key}' must be true/false.")

    if field.type == "select":
        if not isinstance(raw, str):
            raise ValueError(f"Field '{field.key}' must be a string option.")
        valid_values = {option.value for option in field.options or []}
        if raw not in valid_values:
            raise ValueError(f"Field '{field.key}' contains an invalid option.")
        return raw

    raise ValueError(f"Unsupported field type '{field.type}'.")
