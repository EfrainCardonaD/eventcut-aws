import os
import socket

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from auth.core.settings import settings
from auth.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
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
                detail={"status": "degraded", "service": "auth-service", "node_id": node_id, "database": f"error: {exc}"},
            ) from exc

    return {
        "status": "ok",
        "service": settings.app_name,
        "node_id": node_id,
        "availability_zone": az,
        "database": db_status,
    }
