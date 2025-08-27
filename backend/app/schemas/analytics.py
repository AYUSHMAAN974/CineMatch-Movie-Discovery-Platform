"""
Analytics Pydantic schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class UserTasteProfile(BaseModel):
    """User taste profile schema"""
    user_id: uuid.UUID
    genre_preferences: Dict[str, Any] = {}
    decade_preferences: Dict[str, Any] = {}
    language_preferences: Dict[str, Any] = {}
    runtime_preferences: Dict[str, Any] = {}
    mood_preferences: Dict[str, float] = {}
    total_ratings: int = 0
    average_rating: float = 0.0
    rating_variance: float = 0.0
    diversity_score: float = 0.0
    last_updated: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ViewingPatterns(BaseModel):
    """User viewing patterns schema"""
    user_id: uuid.UUID
    analysis_period_days: int
    total_activities: int = 0
    hourly_activity: Dict[str, int] = {}
    daily_activity: Dict[str, int] = {}
    activity_types: Dict[str, int] = {}
    peak_activity_hour: int = 0
    peak_activity_day: int = 0
    average_rating_interval_hours: float = 0.0
    most_active_day_name: str = ""
    total_ratings_period: int = 0
    binge_watching_score: float = 0.0
    
    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Comprehensive user statistics schema"""
    user_id: uuid.UUID
    total_ratings: int = 0
    total_reviews: int = 0
    total_activities: int = 0
    recent_activity_count: int = 0
    average_rating: float = 0.0
    most_rated_genre: Optional[str] = None
    rating_distribution: Dict[str, int] = {}
    account_age_days: int = 0
    engagement_score: float = 0.0
    
    class Config:
        from_attributes = True


class RecommendationPerformance(BaseModel):
    """Recommendation performance metrics schema"""
    user_id: uuid.UUID
    total_recommendations_received: int = 0
    recommendations_acted_on: int = 0
    click_through_rate: float = 0.0
    average_rating_of_recommended: float = 0.0
    recommendation_accuracy: float = 0.0
    favorite_recommendation_type: str = "personal"
    
    class Config:
        from_attributes = True


class MovieTrendAnalysis(BaseModel):
    """Movie trend analysis schema"""
    analysis_period_days: int
    genre_filter: Optional[str] = None
    most_viewed_movies: List[Dict[str, Any]] = []
    most_rated_movies: List[Dict[str, Any]] = []
    trending_genres: List[Dict[str, Any]] = []
    total_activities: int = 0
    peak_activity_date: Optional[str] = None
    
    class Config:
        from_attributes = True