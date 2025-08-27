"""
User-related Pydantic schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, field_validator, Field
from datetime import datetime
import uuid


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=500)
    is_active: bool = True


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v


class UserUpdate(BaseModel):
    """Schema for user updates"""
    full_name: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None
    favorite_genres: Optional[List[str]] = None
    preferred_languages: Optional[str] = None
    content_rating_preference: Optional[str] = "PG-13"


class UserInDB(UserBase):
    """User schema as stored in database"""
    id: uuid.UUID
    hashed_password: str
    is_verified: bool = False
    is_premium: bool = False
    created_at: datetime
    updated_at: Optional[datetime]
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class User(UserBase):
    """Public user schema (for API responses)"""
    id: uuid.UUID
    is_verified: bool
    is_premium: bool
    created_at: datetime
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class UserProfile(User):
    """Extended user profile with additional information"""
    favorite_genres: Optional[List[str]] = None
    preferred_languages: Optional[str] = None
    total_ratings: Optional[int] = 0
    total_reviews: Optional[int] = 0
    total_watchlist: Optional[int] = 0
    average_rating: Optional[float] = 0.0
    taste_profile: Optional[Dict[str, Any]] = None


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences"""
    favorite_genres: Optional[List[str]] = None
    preferred_languages: Optional[str] = None
    content_rating_preference: Optional[str] = None
    preferred_movie_length: Optional[str] = None
    preferred_release_year_min: Optional[int] = None
    preferred_release_year_max: Optional[int] = None
    share_ratings_publicly: Optional[bool] = None
    allow_friend_recommendations: Optional[bool] = None
    receive_notifications: Optional[bool] = None
    recommendation_diversity: Optional[float] = Field(None, ge=0.0, le=1.0)


class UserStats(BaseModel):
    """User statistics"""
    total_movies_rated: int = 0
    total_reviews_written: int = 0
    total_watchlist_items: int = 0
    average_rating: float = 0.0
    most_rated_genre: Optional[str] = None
    rating_distribution: Optional[Dict[str, int]] = None
    recent_activity_count: int = 0


class UserActivity(BaseModel):
    """User activity schema"""
    id: uuid.UUID
    activity_type: str
    movie_id: Optional[int] = None
    movie_title: Optional[str] = None
    created_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True