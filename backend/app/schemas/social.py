"""
Social features Pydantic schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class FriendshipBase(BaseModel):
    """Base friendship schema"""
    pass


class FriendshipCreate(BaseModel):
    """Schema for creating friendship request"""
    friend_username: str = Field(..., min_length=3, max_length=50)
    message: Optional[str] = Field(None, max_length=500)


class FriendshipUpdate(BaseModel):
    """Schema for updating friendship status"""
    status: str = Field(..., pattern="^(accepted|declined|blocked)$")


class Friendship(BaseModel):
    """Complete friendship schema"""
    id: uuid.UUID
    user_id: uuid.UUID
    friend_id: uuid.UUID
    status: str
    message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    
    # Related data
    friend_username: Optional[str] = None
    friend_full_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class WatchPartyBase(BaseModel):
    """Base watch party schema"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    movie_id: Optional[int] = None


class WatchPartyCreate(WatchPartyBase):
    """Schema for creating watch party"""
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0, lt=600)
    is_public: bool = False
    max_participants: int = Field(10, ge=2, le=50)
    allow_movie_suggestions: bool = True
    require_approval: bool = True


class WatchPartyUpdate(BaseModel):
    """Schema for updating watch party"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    movie_id: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(planning|active|completed|cancelled)$")


class WatchParty(WatchPartyBase):
    """Complete watch party schema"""
    id: uuid.UUID
    creator_id: uuid.UUID
    scheduled_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    is_public: bool = False
    max_participants: int = 10
    allow_movie_suggestions: bool = True
    require_approval: bool = True
    status: str = "planning"
    invitation_code: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Related data
    creator_username: Optional[str] = None
    movie_title: Optional[str] = None
    participant_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


class WatchPartyList(BaseModel):
    """Watch party list response schema"""
    watch_parties: List[WatchParty]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class WatchPartyMemberBase(BaseModel):
    """Base watch party member schema"""
    pass


class WatchPartyJoin(BaseModel):
    """Schema for joining watch party"""
    invitation_code: Optional[str] = None


class WatchPartyMember(BaseModel):
    """Complete watch party member schema"""
    id: uuid.UUID
    watch_party_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    role: str
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    is_present: bool = False
    created_at: datetime
    
    # Related data
    username: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class SocialRecommendationBase(BaseModel):
    """Base social recommendation schema"""
    recipient_id: uuid.UUID
    movie_id: int
    message: Optional[str] = Field(None, max_length=500)
    rating: Optional[int] = Field(None, ge=1, le=5)


class SocialRecommendationCreate(SocialRecommendationBase):
    """Schema for creating social recommendation"""
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class SocialRecommendation(SocialRecommendationBase):
    """Complete social recommendation schema"""
    id: uuid.UUID
    sender_id: uuid.UUID
    confidence: Optional[float] = None
    is_viewed: bool = False
    is_accepted: Optional[bool] = None
    recipient_rating: Optional[int] = None
    created_at: datetime
    viewed_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    
    # Related data
    sender_username: Optional[str] = None
    sender_full_name: Optional[str] = None
    movie_title: Optional[str] = None
    movie_poster_url: Optional[str] = None
    
    class Config:
        from_attributes = True