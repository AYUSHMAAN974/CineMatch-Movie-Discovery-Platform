"""
Rating and review-related Pydantic schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import uuid


class RatingBase(BaseModel):
    """Base rating schema"""
    rating: float = Field(..., ge=0.5, le=5.0)
    movie_id: int
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        # Ensure rating is in 0.5 increments
        if v * 2 != int(v * 2):
            raise ValueError('Rating must be in 0.5 increments (0.5, 1.0, 1.5, etc.)')
        return v


class RatingCreate(RatingBase):
    """Schema for creating ratings"""
    is_favorite: Optional[bool] = False
    is_watchlist: Optional[bool] = False
    rating_context: Optional[str] = Field(None, max_length=50)
    mood_when_watched: Optional[str] = Field(None, max_length=50)
    watched_date: Optional[datetime] = None


class RatingUpdate(BaseModel):
    """Schema for updating ratings"""
    rating: Optional[float] = Field(None, ge=0.5, le=5.0)
    is_favorite: Optional[bool] = None
    is_watchlist: Optional[bool] = None
    rating_context: Optional[str] = Field(None, max_length=50)
    mood_when_watched: Optional[str] = Field(None, max_length=50)
    watched_date: Optional[datetime] = None
    
    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v is not None and v * 2 != int(v * 2):
            raise ValueError('Rating must be in 0.5 increments (0.5, 1.0, 1.5, etc.)')
        return v


class Rating(RatingBase):
    """Complete rating schema for responses"""
    id: uuid.UUID
    user_id: uuid.UUID
    is_favorite: bool
    is_watchlist: bool
    rating_context: Optional[str] = None
    mood_when_watched: Optional[str] = None
    watched_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    movie_title: Optional[str] = None  # Added for convenience
    
    class Config:
        from_attributes = True


class ReviewBase(BaseModel):
    """Base review schema"""
    movie_id: int
    content: str = Field(..., min_length=10, max_length=5000)
    title: Optional[str] = Field(None, max_length=200)
    rating: Optional[float] = Field(None, ge=0.5, le=5.0)
    is_spoiler: Optional[bool] = False
    is_recommended: Optional[bool] = True


class ReviewCreate(ReviewBase):
    """Schema for creating reviews"""
    pass


class ReviewUpdate(BaseModel):
    """Schema for updating reviews"""
    content: Optional[str] = Field(None, min_length=10, max_length=5000)
    title: Optional[str] = Field(None, max_length=200)
    rating: Optional[float] = Field(None, ge=0.5, le=5.0)
    is_spoiler: Optional[bool] = None
    is_recommended: Optional[bool] = None


class Review(ReviewBase):
    """Complete review schema for responses"""
    id: uuid.UUID
    user_id: uuid.UUID
    helpful_count: int = 0
    report_count: int = 0
    is_approved: bool = True
    is_featured: bool = False
    sentiment_score: Optional[float] = None
    emotion_tags: Optional[List[str]] = None
    spoiler_probability: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related data
    user_username: Optional[str] = None
    movie_title: Optional[str] = None
    user_helpful_vote: Optional[bool] = None  # Current user's helpful vote
    
    class Config:
        from_attributes = True


class ReviewList(BaseModel):
    """Review list response schema"""
    reviews: List[Review]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ReviewHelpfulVote(BaseModel):
    """Schema for voting on review helpfulness"""
    is_helpful: bool


class WatchlistItemBase(BaseModel):
    """Base watchlist item schema"""
    movie_id: int


class WatchlistItemCreate(WatchlistItemBase):
    """Schema for adding to watchlist"""
    priority: Optional[int] = Field(5, ge=1, le=10)
    notes: Optional[str] = Field(None, max_length=500)
    added_reason: Optional[str] = Field(None, max_length=200)


class WatchlistItemUpdate(BaseModel):
    """Schema for updating watchlist items"""
    priority: Optional[int] = Field(None, ge=1, le=10)
    notes: Optional[str] = Field(None, max_length=500)
    is_watched: Optional[bool] = None
    watched_date: Optional[datetime] = None


class WatchlistItem(WatchlistItemBase):
    """Complete watchlist item schema"""
    id: uuid.UUID
    user_id: uuid.UUID
    priority: int
    notes: Optional[str] = None
    added_reason: Optional[str] = None
    is_watched: bool = False
    watched_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related data
    movie_title: Optional[str] = None
    movie_poster_url: Optional[str] = None
    movie_year: Optional[int] = None
    movie_genres: Optional[List[str]] = None
    
    class Config:
        from_attributes = True


class WatchlistResponse(BaseModel):
    """Watchlist response schema"""
    items: List[WatchlistItem]
    total: int
    watched_count: int
    unwatched_count: int
    total_runtime: Optional[int] = None  # Total runtime of unwatched movies


class RatingStats(BaseModel):
    """User rating statistics"""
    total_ratings: int = 0
    average_rating: float = 0.0
    rating_distribution: Dict[str, int] = {}
    favorite_genres: List[Dict[str, Any]] = []
    most_rated_year: Optional[int] = None
    rating_trend: Optional[List[Dict[str, Any]]] = []


class UserRatingsResponse(BaseModel):
    """User ratings response schema"""
    ratings: List[Rating]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    stats: Optional[RatingStats] = None