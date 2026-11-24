from fastapi import APIRouter

from events_service.app.api.routes.admin import router as admin_router
from events_service.app.api.routes.categories import router as categories_router
from events_service.app.api.routes.communities import router as communities_router
from events_service.app.api.routes.events import router as events_router
from events_service.app.api.routes.health import router as health_router
from events_service.app.api.routes.storage import router as storage_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(categories_router)
api_router.include_router(events_router)
api_router.include_router(communities_router)
api_router.include_router(admin_router)
api_router.include_router(storage_router, prefix="/v1/events")
api_router.include_router(storage_router, prefix="/v1/communities")
