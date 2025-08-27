"""
Main API router that includes all endpoint routers
"""
from fastapi import APIRouter

from app.api.v1 import auth, movies, recommendations, ratings, social, analytics
from app.core.config import settings

api_router = APIRouter(prefix=settings.API_V1_STR)

# Include all routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["authentication"]
)

api_router.include_router(
    movies.router,
    prefix="/movies",
    tags=["movies"]
)

api_router.include_router(
    recommendations.router,
    prefix="/recommendations",
    tags=["recommendations"]
)

api_router.include_router(
    ratings.router,
    prefix="/ratings",
    tags=["ratings"]
)

api_router.include_router(
    social.router,
    prefix="/social",
    tags=["social"]
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)