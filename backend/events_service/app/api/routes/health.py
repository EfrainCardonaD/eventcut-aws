import os
import socket

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from events_service.app.core.settings import settings
from events_service.app.db.session import engine
from events_service.app.schemas.common import ApiResponse
from events_service.app.services.storage_service import get_bucket_name

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> ApiResponse[dict[str, str]]:
    node_id = os.getenv("EC2_INSTANCE_ID") or socket.gethostname()
    az = os.getenv("AWS_AZ") or "local"
    db_status = "skipped"

    check_db = os.getenv("HEALTH_CHECK_DB", "true" if settings.app_env == "prod" else "false").lower() == "true"
    if check_db:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"RDS MySQL unreachable on node {node_id}: {exc}",
            ) from exc

    return ApiResponse(
        success=True,
        message="Servicio operativo",
        data={
            "status": "ok",
            "service": settings.app_name,
            "node_id": node_id,
            "availability_zone": az,
            "database": db_status,
            "storage_provider": "aws_s3",
            "storage_bucket": get_bucket_name() or "not-configured",
        },
    )
