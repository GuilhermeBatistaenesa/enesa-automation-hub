from __future__ import annotations

import urllib.parse
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Enesa Automation Hub API"
    environment: str = "dev"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_format: str = "json"

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"
    auth_mode: str = "hybrid"
    allow_local_auth: bool = True

    sql_server_host: str = "localhost"
    sql_server_port: int = 1433
    sql_server_database: str = "enesa_automation_hub"
    sql_server_user: str = "sa"
    sql_server_password: str = ""
    sql_server_driver: str = "ODBC Driver 18 for SQL Server"
    sql_server_trust_server_certificate: bool = True
    sql_server_odbc_extra: str = ""

    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "enesa:runs:queue"
    redis_pubsub_prefix: str = "enesa:runs"

    artifacts_root: Path = Field(default=Path("./data/artifacts"))
    python_executable: str = "python"
    artifact_retention_days: int = 90
    log_retention_days: int = 90
    cleanup_interval_hours: int = 24

    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1"

    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"
    default_admin_email: str = "admin@enesa.local"

    azure_ad_tenant_id: str | None = None
    azure_ad_client_id: str | None = None
    azure_ad_audience: str | None = None
    azure_ad_issuer: str | None = None
    azure_ad_jwks_url: str | None = None
    azure_ad_group_admin_ids: str = ""
    azure_ad_group_operator_ids: str = ""
    azure_ad_group_viewer_ids: str = ""
    auto_provision_azure_users: bool = True

    @property
    def sqlalchemy_database_uri(self) -> str:
        trust = "yes" if self.sql_server_trust_server_certificate else "no"
        conn_parts = [
            f"DRIVER={{{self.sql_server_driver}}}",
            f"SERVER={self.sql_server_host},{self.sql_server_port}",
            f"DATABASE={self.sql_server_database}",
            f"UID={self.sql_server_user}",
            f"PWD={self.sql_server_password}",
            f"TrustServerCertificate={trust}",
        ]
        if self.sql_server_odbc_extra:
            conn_parts.append(self.sql_server_odbc_extra)
        conn_str = ";".join(conn_parts)
        return f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_hosts.split(",") if item.strip()]

    @property
    def azure_enabled(self) -> bool:
        return bool(self.azure_ad_tenant_id and self.azure_ad_client_id and self.azure_ad_audience)

    @property
    def resolved_azure_issuer(self) -> str | None:
        if self.azure_ad_issuer:
            return self.azure_ad_issuer
        if not self.azure_ad_tenant_id:
            return None
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/v2.0"

    @property
    def resolved_azure_jwks_url(self) -> str | None:
        if self.azure_ad_jwks_url:
            return self.azure_ad_jwks_url
        if not self.azure_ad_tenant_id:
            return None
        return f"https://login.microsoftonline.com/{self.azure_ad_tenant_id}/discovery/v2.0/keys"

    @property
    def azure_group_admin_list(self) -> set[str]:
        return _csv_to_set(self.azure_ad_group_admin_ids)

    @property
    def azure_group_operator_list(self) -> set[str]:
        return _csv_to_set(self.azure_ad_group_operator_ids)

    @property
    def azure_group_viewer_list(self) -> set[str]:
        return _csv_to_set(self.azure_ad_group_viewer_ids)

    def run_channel(self, run_id: str) -> str:
        return f"{self.redis_pubsub_prefix}:{run_id}:logs"


def _csv_to_set(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

