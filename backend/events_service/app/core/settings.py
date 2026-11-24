from __future__ import annotations

from typing import List


from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("events_service/.env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="events-service", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")

    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )
    trusted_hosts: str = Field(default="localhost,127.0.0.1", alias="TRUSTED_HOSTS")
    app_force_https: bool = Field(default=False, alias="APP_FORCE_HTTPS")

    jwt_secret_key: str = Field(default="change-me", alias="JWT_SECRET_KEY")
    jwt_issuer: str = Field(default="microservices-app", alias="JWT_ISSUER")

    auth_service_base_url: str = Field(default="http://127.0.0.1:8000", alias="AUTH_SERVICE_BASE_URL")
    app_gateway_secret: str = Field(default="default-secret-change-me", alias="APP_GATEWAY_SECRET")
    auth_remote_validation_enabled: bool = Field(default=True, alias="AUTH_REMOTE_VALIDATION_ENABLED")

    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_db: str = Field(default="eventcut_events_db", alias="MYSQL_DB")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="root", alias="MYSQL_PASSWORD")
    mysql_pool_size: int = Field(default=20, alias="MYSQL_POOL_SIZE")
    mysql_max_overflow: int = Field(default=10, alias="MYSQL_MAX_OVERFLOW")

    public_read_rate_limit_requests: int = Field(default=60, alias="PUBLIC_READ_RATE_LIMIT_REQUESTS")
    public_read_rate_limit_window_seconds: int = Field(default=60, alias="PUBLIC_READ_RATE_LIMIT_WINDOW_SECONDS")
    max_pagination_offset: int = Field(default=2000, alias="MAX_PAGINATION_OFFSET")
    upload_max_image_size_bytes: int = Field(default=15 * 1024 * 1024, alias="UPLOAD_MAX_IMAGE_SIZE_BYTES")
    upload_presigned_url_ttl_seconds: int = Field(default=300, alias="UPLOAD_PRESIGNED_URL_TTL_SECONDS")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )

    def parsed_cors_allowed_origins(self) -> List[str]:
        # CORS en Starlette compara strings exactos del header Origin.
        # Por eso deben incluir esquema (https://) y no sólo el host.
        return [o.strip().rstrip("/") for o in self.cors_allowed_origins.split(",") if o.strip()]

    def parsed_trusted_hosts(self) -> List[str]:
        # TrustedHostMiddleware permite comodines, ej: "*.ngrok-free.dev".
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    def parsed_auth_service_base_urls(self) -> List[str]:
        # Permite definir múltiples URLs separadas por coma.
        return [u.strip().rstrip("/") for u in self.auth_service_base_url.split(",") if u.strip()]


settings = Settings()

