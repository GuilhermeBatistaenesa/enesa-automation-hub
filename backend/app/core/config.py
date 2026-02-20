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

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

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

    cors_origins: str = "http://localhost:3000"

    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"
    default_admin_email: str = "admin@enesa.local"

    azure_ad_tenant_id: str | None = None
    azure_ad_client_id: str | None = None
    azure_ad_audience: str | None = None

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

    def run_channel(self, run_id: str) -> str:
        return f"{self.redis_pubsub_prefix}:{run_id}:logs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

