"""API v1 Router - Aggregates all API endpoints"""

from fastapi import APIRouter

from app.api.v1.endpoints import query, kg, feedback, settings, sessions

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    query.router,
    prefix="/query",
    tags=["Query"]
)

api_router.include_router(
    kg.router,
    prefix="/kg",
    tags=["Knowledge Graph"]
)

api_router.include_router(
    feedback.router,
    prefix="/feedback",
    tags=["Feedback"]
)

api_router.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"]
)

api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["Sessions"]
)
