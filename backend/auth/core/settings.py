from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_auth_env_file() -> Path:
    env_file = os.getenv("AUTH_ENV_FILE")
    if env_file:
        return Path(env_file).expanduser()
    return Path(__file__).resolve().parents[1] / ".env"


_AUTH_ENV_FILE = _get_auth_env_file()
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_AUTH_ENV_FILE),),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="auth-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")

    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )
    trusted_hosts: str = Field(default="localhost,127.0.0.1", alias="TRUSTED_HOSTS")
    app_force_https: bool = Field(default=False, alias="APP_FORCE_HTTPS")

    # Gateway secret (para endpoints internos)
    app_gateway_secret: str = Field(default="default-secret-change-me", alias="APP_GATEWAY_SECRET")
    app_gateway_validation_enabled: bool = Field(default=False, alias="APP_GATEWAY_VALIDATION_ENABLED")

    # JWT (HS256)
    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_issuer: str = Field(default="microservices-app", alias="JWT_ISSUER")
    jwt_access_expiration_minutes: int = Field(default=10, alias="JWT_ACCESS_EXPIRATION_MINUTES")
    # Compatibilidad hacia atrás con despliegues que aún usan la variable antigua.
    jwt_expiration_hours_legacy: int | None = Field(default=None, alias="JWT_EXPIRATION_HOURS")
    jwt_refresh_expiration_days: int = Field(default=30, alias="JWT_REFRESH_EXPIRATION_DAYS")

    # MySQL
    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="auth_db", alias="MYSQL_DB")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="root", alias="MYSQL_PASSWORD")

    # SMTP / Mail
    app_mail_enabled: bool = Field(default=False, alias="APP_MAIL_ENABLED")
    app_mail_from: str = Field(default="noreply@example.com", alias="APP_MAIL_FROM")
    mail_host: str = Field(default="smtp.example.com", alias="MAIL_HOST")
    mail_port: int = Field(default=587, alias="MAIL_PORT")
    mail_username: str = Field(default="", alias="MAIL_USERNAME")
    mail_password: str = Field(default="", alias="MAIL_PASSWORD")
    mail_use_tls: bool = Field(default=True, alias="MAIL_USE_TLS")

    app_frontend_base_url: str = Field(default="http://localhost:3000", alias="APP_FRONTEND_BASE_URL")

    # Tokens (verificación / reset)
    verification_token_ttl_minutes: int = Field(default=60, alias="VERIFICATION_TOKEN_TTL_MINUTES")
    reset_token_ttl_minutes: int = Field(default=30, alias="RESET_TOKEN_TTL_MINUTES")

    auth_login_rate_limit_requests: int = Field(default=5, alias="AUTH_LOGIN_RATE_LIMIT_REQUESTS")
    auth_login_rate_limit_window_seconds: int = Field(default=60, alias="AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    auth_recovery_rate_limit_requests: int = Field(default=3, alias="AUTH_RECOVERY_RATE_LIMIT_REQUESTS")
    auth_recovery_rate_limit_window_seconds: int = Field(default=600, alias="AUTH_RECOVERY_RATE_LIMIT_WINDOW_SECONDS")
    auth_token_action_rate_limit_requests: int = Field(default=10, alias="AUTH_TOKEN_ACTION_RATE_LIMIT_REQUESTS")
    auth_token_action_rate_limit_window_seconds: int = Field(default=60, alias="AUTH_TOKEN_ACTION_RATE_LIMIT_WINDOW_SECONDS")

    @property
    def database_url(self) -> str:
        # SQLAlchemy URL (sync)
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    def parsed_cors_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    def parsed_trusted_hosts(self) -> List[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def jwt_access_ttl_minutes(self) -> int:
        if self.jwt_access_expiration_minutes > 0:
            return self.jwt_access_expiration_minutes
        if self.jwt_expiration_hours_legacy and self.jwt_expiration_hours_legacy > 0:
            return self.jwt_expiration_hours_legacy * 60
        return 10


settings = Settings()
