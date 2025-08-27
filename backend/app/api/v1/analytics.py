"""
Analytics and user insights endpoints
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.user import User
from app.schemas.analytics import (
    UserTasteProfile, ViewingPatterns, UserStats,
    MovieTrendAnalysis, RecommendationPerformance
)
from app.services.analytics_service import AnalyticsService
from app.utils.dependencies import get_current_active_user
from app.services.cache.redis_client import RedisCache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/taste-profile", response_model=UserTasteProfile)
async def get_user_taste_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get detailed analysis of user's movie taste and preferences
    """
    try:
        analytics_service = AnalyticsService(db)
        cache = RedisCache()
        
        cache_key = f"taste_profile_{current_user.id}"
        cached_profile = await cache.get(cache_key)
        
        if cached_profile:
            return cached_profile
        
        taste_profile = analytics_service.get_user_taste_profile(current_user.id)
        
        # Cache for 1 hour
        await cache.set(cache_key, taste_profile.dict(), ttl=3600)
        
        return taste_profile
        
    except Exception as e:
        logger.error(f"Error fetching user taste profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user taste profile"
        )


@router.get("/viewing-patterns", response_model=ViewingPatterns)
async def get_viewing_patterns(
    days: int = Query(30, ge=7, le=365, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user's viewing patterns and behavior analysis
    """
    try:
        analytics_service = AnalyticsService(db)
        
        viewing_patterns = analytics_service.get_viewing_patterns(
            user_id=current_user.id,
            days=days
        )
        
        return viewing_patterns
        
    except Exception as e:
        logger.error(f"Error fetching viewing patterns: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch viewing patterns"
        )


@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get comprehensive user statistics
    """
    try:
        analytics_service = AnalyticsService(db)
        cache = RedisCache()
        
        cache_key = f"user_stats_{current_user.id}"
        cached_stats = await cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        user_stats = analytics_service.get_user_statistics(current_user.id)
        
        # Cache for 30 minutes
        await cache.set(cache_key, user_stats.dict(), ttl=1800)
        
        return user_stats
        
    except Exception as e:
        logger.error(f"Error fetching user stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user statistics"
        )


@router.get("/recommendation-performance", response_model=RecommendationPerformance)
async def get_recommendation_performance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get performance metrics for user's recommendations
    """
    try:
        analytics_service = AnalyticsService(db)
        
        performance = analytics_service.get_recommendation_performance(current_user.id)
        
        return performance
        
    except Exception as e:
        logger.error(f"Error fetching recommendation performance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recommendation performance"
        )


@router.post("/interaction")
async def track_interaction(
    interaction_type: str,
    movie_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Track user interaction for analytics
    """
    try:
        from app.tasks.analytics_tasks import track_user_activity
        
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type=interaction_type,
            movie_id=movie_id,
            metadata=metadata or {}
        )
        
        return {"message": "Interaction tracked successfully"}
        
    except Exception as e:
        logger.error(f"Error tracking interaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track interaction"
        )


@router.get("/trends", response_model=MovieTrendAnalysis)
async def get_movie_trends(
    genre: Optional[str] = Query(None, description="Filter by genre"),
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movie trend analysis
    """
    try:
        analytics_service = AnalyticsService(db)
        cache = RedisCache()
        
        cache_key = f"movie_trends_{genre or 'all'}_{days}"
        cached_trends = await cache.get(cache_key)
        
        if cached_trends:
            return cached_trends
        
        trends = analytics_service.get_movie_trends(
            genre=genre,
            days=days
        )
        
        # Cache for 2 hours
        await cache.set(cache_key, trends.dict(), ttl=7200)
        
        return trends
        
    except Exception as e:
        logger.error(f"Error fetching movie trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch movie trends"
        )