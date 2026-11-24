from fastapi import APIRouter

from auth.api.routes.auth import router as auth_router
from auth.api.routes.health import router as health_router
from auth.api.routes.internal_auth import router as internal_auth_router
from auth.api.routes.internal_users import router as internal_users_router
from auth.api.routes.password_recovery import router as password_recovery_router
from auth.api.routes.users import router as users_router
from auth.api.routes.verify import router as verify_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(password_recovery_router)
api_router.include_router(verify_router)
api_router.include_router(internal_auth_router)
api_router.include_router(internal_users_router)
api_router.include_router(users_router)
