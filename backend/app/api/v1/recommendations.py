"""
AI-powered recommendation endpoints
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.models.user import User
from app.schemas.movie import Movie
from app.services.ml.recommendation_engine import RecommendationEngine
from app.services.ml.hybrid_recommender import HybridRecommender
from app.services.cache.redis_client import RedisCache
from app.utils.dependencies import get_current_active_user
from app.tasks.recommendation_tasks import generate_user_recommendations

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/personal", response_model=List[Movie])
async def get_personal_recommendations(
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    refresh: bool = Query(False, description="Force refresh recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get personalized movie recommendations for the current user
    """
    try:
        cache = RedisCache()
        cache_key = f"recommendations_personal_{current_user.id}_{limit}"
        
        # Check cache unless refresh is requested
        if not refresh:
            cached_recommendations = await cache.get(cache_key)
            if cached_recommendations:
                return cached_recommendations
        
        # Generate recommendations using hybrid approach
        recommender = HybridRecommender(db)
        recommendations = await recommender.get_personal_recommendations(
            user_id=current_user.id,
            limit=limit
        )
        
        # Cache recommendations for 30 minutes
        await cache.set(cache_key, [rec.dict() for rec in recommendations], ttl=1800)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating personal recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate personal recommendations"
        )


@router.get("/mood/{mood}", response_model=List[Movie])
async def get_mood_based_recommendations(
    mood: str,
    limit: int = Query(10, ge=1, le=30, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get mood-based movie recommendations
    """
    try:
        # Validate mood
        valid_moods = [
            "happy", "sad", "excited", "romantic", "adventurous", 
            "relaxed", "thoughtful", "scared", "nostalgic", "energetic"
        ]
        
        if mood.lower() not in valid_moods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mood. Valid options: {', '.join(valid_moods)}"
            )
        
        cache = RedisCache()
        cache_key = f"recommendations_mood_{mood}_{current_user.id}_{limit}"
        
        # Check cache
        cached_recommendations = await cache.get(cache_key)
        if cached_recommendations:
            return cached_recommendations
        
        # Generate mood-based recommendations
        from app.services.ml.mood_analyzer import MoodAnalyzer
        mood_analyzer = MoodAnalyzer(db)
        
        recommendations = await mood_analyzer.get_mood_recommendations(
            user_id=current_user.id,
            mood=mood.lower(),
            limit=limit
        )
        
        # Cache for 1 hour
        await cache.set(cache_key, [rec.dict() for rec in recommendations], ttl=3600)
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating mood recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate mood-based recommendations"
        )


@router.get("/similar/{movie_id}", response_model=List[Movie])
async def get_similar_movie_recommendations(
    movie_id: int,
    limit: int = Query(10, ge=1, le=30, description="Number of similar movies"),
    current_user: Optional[User] = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movies similar to a specific movie using content-based filtering
    """
    try:
        cache = RedisCache()
        user_suffix = f"_{current_user.id}" if current_user else ""
        cache_key = f"recommendations_similar_{movie_id}{user_suffix}_{limit}"
        
        # Check cache
        cached_recommendations = await cache.get(cache_key)
        if cached_recommendations:
            return cached_recommendations
        
        # Generate similar movie recommendations
        from app.services.ml.content_based import ContentBasedRecommender
        content_recommender = ContentBasedRecommender(db)
        
        recommendations = await content_recommender.get_similar_movies(
            movie_id=movie_id,
            user_id=current_user.id if current_user else None,
            limit=limit
        )
        
        # Cache for 4 hours
        await cache.set(cache_key, [rec.dict() for rec in recommendations], ttl=14400)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating similar movie recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate similar movie recommendations"
        )


@router.get("/trending-for-you", response_model=List[Movie])
async def get_personalized_trending(
    limit: int = Query(10, ge=1, le=30, description="Number of trending movies"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get trending movies personalized for the user
    """
    try:
        cache = RedisCache()
        cache_key = f"recommendations_trending_{current_user.id}_{limit}"
        
        # Check cache
        cached_recommendations = await cache.get(cache_key)
        if cached_recommendations:
            return cached_recommendations
        
        # Get personalized trending movies
        recommender = HybridRecommender(db)
        recommendations = await recommender.get_personalized_trending(
            user_id=current_user.id,
            limit=limit
        )
        
        # Cache for 2 hours
        await cache.set(cache_key, [rec.dict() for rec in recommendations], ttl=7200)
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating personalized trending: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate personalized trending movies"
        )


@router.get("/group", response_model=List[Movie])
async def get_group_recommendations(
    user_ids: List[str] = Query(..., description="List of user IDs for group recommendations"),
    limit: int = Query(10, ge=1, le=20, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movie recommendations for a group of users (watch party matching)
    """
    try:
        # Validate user IDs and ensure current user is included
        if str(current_user.id) not in user_ids:
            user_ids.append(str(current_user.id))
        
        # Limit group size
        if len(user_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group size cannot exceed 10 users"
            )
        
        cache = RedisCache()
        cache_key = f"recommendations_group_{'_'.join(sorted(user_ids))}_{limit}"
        
        # Check cache
        cached_recommendations = await cache.get(cache_key)
        if cached_recommendations:
            return cached_recommendations
        
        # Generate group recommendations
        from app.services.ml.group_recommender import GroupRecommender
        group_recommender = GroupRecommender(db)
        
        recommendations = await group_recommender.get_group_recommendations(
            user_ids=user_ids,
            limit=limit
        )
        
        # Cache for 1 hour
        await cache.set(cache_key, [rec.dict() for rec in recommendations], ttl=3600)
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating group recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate group recommendations"
        )


@router.post("/feedback")
async def provide_recommendation_feedback(
    movie_id: int,
    feedback_type: str = Query(..., regex="^(like|dislike|not_interested|watched)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Provide feedback on recommendations to improve future suggestions
    """
    try:
        # Track feedback for improving recommendations
        from app.tasks.analytics_tasks import track_recommendation_feedback
        track_recommendation_feedback.delay(
            user_id=str(current_user.id),
            movie_id=movie_id,
            feedback_type=feedback_type
        )
        
        # Trigger recommendation model update if needed
        from app.tasks.recommendation_tasks import update_user_taste_profile
        update_user_taste_profile.delay(str(current_user.id))
        
        return {"message": "Feedback recorded successfully"}
        
    except Exception as e:
        logger.error(f"Error recording recommendation feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record recommendation feedback"
        )


@router.post("/refresh")
async def refresh_recommendations(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Trigger refresh of user's recommendations
    """
    try:
        # Clear cached recommendations
        cache = RedisCache()
        user_id = str(current_user.id)
        
        # Clear all recommendation caches for this user
        cache_patterns = [
            f"recommendations_personal_{user_id}_*",
            f"recommendations_mood_*_{user_id}_*",
            f"recommendations_trending_{user_id}_*"
        ]
        
        for pattern in cache_patterns:
            await cache.delete_pattern(pattern)
        
        # Trigger background task to regenerate recommendations
        task = generate_user_recommendations.delay(user_id)
        
        return {
            "message": "Recommendation refresh initiated",
            "task_id": task.id
        }
        
    except Exception as e:
        logger.error(f"Error refreshing recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh recommendations"
        )


@router.get("/explanation/{movie_id}")
async def get_recommendation_explanation(
    movie_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get explanation for why a movie was recommended
    """
    try:
        recommender = HybridRecommender(db)
        explanation = await recommender.explain_recommendation(
            user_id=current_user.id,
            movie_id=movie_id
        )
        
        if not explanation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No explanation available for this recommendation"
            )
        
        return explanation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recommendation explanation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recommendation explanation"
        )