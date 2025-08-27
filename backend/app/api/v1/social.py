"""
Social features endpoints
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.models.user import User
from app.schemas.movie import Movie  # ← ADD THIS LINE
from app.schemas.social import (
    Friendship, FriendshipCreate, FriendshipUpdate,
    WatchParty, WatchPartyCreate, WatchPartyUpdate, WatchPartyList,
    WatchPartyMember, WatchPartyJoin,
    SocialRecommendation, SocialRecommendationCreate
)
from app.services.social_service import SocialService
from app.utils.dependencies import get_current_active_user
from app.tasks.analytics_tasks import track_user_activity

logger = logging.getLogger(__name__)
router = APIRouter()


# Friendship endpoints
@router.post("/friends/request", response_model=Friendship, status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    friend_request: FriendshipCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Send a friend request to another user
    """
    try:
        social_service = SocialService(db)
        
        # Can't send friend request to yourself
        if friend_request.friend_username == current_user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send friend request to yourself"
            )
        
        # Check if friendship already exists
        existing_friendship = social_service.get_friendship_status(
            current_user.id, 
            friend_request.friend_username
        )
        
        if existing_friendship:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Friendship request already exists or users are already friends"
            )
        
        friendship = social_service.send_friend_request(
            current_user.id,
            friend_request
        )
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="send_friend_request",
            metadata={"friend_username": friend_request.friend_username}
        )
        
        return friendship
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending friend request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send friend request"
        )


@router.put("/friends/{friendship_id}", response_model=Friendship)
async def respond_to_friend_request(
    friendship_id: str,
    response_data: FriendshipUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Accept, decline, or block a friend request
    """
    try:
        social_service = SocialService(db)
        
        # Check if friendship exists and user is the recipient
        friendship = social_service.get_friendship_by_id(friendship_id)
        
        if not friendship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friendship request not found"
            )
        
        if friendship.friend_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot respond to another user's friend request"
            )
        
        updated_friendship = social_service.update_friendship_status(
            friendship_id,
            response_data.status
        )
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="respond_friend_request",
            metadata={"friendship_id": friendship_id, "response": response_data.status}
        )
        
        return updated_friendship
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to friend request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to respond to friend request"
        )


@router.get("/friends", response_model=List[Friendship])
async def get_friends(
    status: Optional[str] = Query(None, pattern="^(pending|accepted|blocked)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user's friends and friend requests
    """
    try:
        social_service = SocialService(db)
        friendships = social_service.get_user_friendships(current_user.id, status)
        
        return friendships
        
    except Exception as e:
        logger.error(f"Error fetching friends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch friends"
        )


@router.get("/friends/recommendations", response_model=List[Movie])
async def get_friend_recommendations(
    limit: int = Query(10, ge=1, le=30, description="Number of recommendations"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movie recommendations based on friends' ratings and preferences
    """
    try:
        from app.services.ml.collaborative import CollaborativeRecommender
        collaborative_recommender = CollaborativeRecommender(db)
        
        recommendations = await collaborative_recommender.get_friend_based_recommendations(
            user_id=current_user.id,
            limit=limit
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error fetching friend recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch friend recommendations"
        )


# Watch Party endpoints
@router.post("/watch-parties", response_model=WatchParty, status_code=status.HTTP_201_CREATED)
async def create_watch_party(
    party_data: WatchPartyCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new watch party
    """
    try:
        social_service = SocialService(db)
        
        watch_party = social_service.create_watch_party(
            creator_id=current_user.id,
            party_data=party_data
        )
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="create_watch_party",
            metadata={"party_name": party_data.name}
        )
        
        return watch_party
        
    except Exception as e:
        logger.error(f"Error creating watch party: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create watch party"
        )


@router.get("/watch-parties", response_model=WatchPartyList)
async def get_watch_parties(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    status: Optional[str] = Query(None, pattern="^(pending|accepted|blocked)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user's watch parties
    """
    try:
        social_service = SocialService(db)
        
        watch_parties = social_service.get_user_watch_parties(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            status=status
        )
        
        return watch_parties
        
    except Exception as e:
        logger.error(f"Error fetching watch parties: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch watch parties"
        )


@router.post("/watch-parties/{party_id}/join", response_model=WatchPartyMember)
async def join_watch_party(
    party_id: str,
    join_data: Optional[WatchPartyJoin] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Join a watch party
    """
    try:
        social_service = SocialService(db)
        
        # Check if party exists
        party = social_service.get_watch_party_by_id(party_id)
        if not party:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watch party not found"
            )
        
        # Check if user is already a member
        if social_service.is_party_member(party_id, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already a member of this watch party"
            )
        
        # Check invitation code if party is private
        if not party.is_public and join_data:
            if join_data.invitation_code != party.invitation_code:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid invitation code"
                )
        
        membership = social_service.join_watch_party(party_id, current_user.id)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="join_watch_party",
            metadata={"party_id": party_id}
        )
        
        return membership
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining watch party: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join watch party"
        )


@router.post("/recommendations", response_model=SocialRecommendation, status_code=status.HTTP_201_CREATED)
async def send_movie_recommendation(
    recommendation_data: SocialRecommendationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Send a movie recommendation to a friend
    """
    try:
        social_service = SocialService(db)
        
        # Check if users are friends
        if not social_service.are_friends(current_user.id, recommendation_data.recipient_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only send recommendations to friends"
            )
        
        recommendation = social_service.send_movie_recommendation(
            sender_id=current_user.id,
            recommendation_data=recommendation_data
        )
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="send_recommendation",
            movie_id=recommendation_data.movie_id,
            metadata={"recipient_id": str(recommendation_data.recipient_id)}
        )
        
        return recommendation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending recommendation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send movie recommendation"
        )


@router.get("/recommendations/received", response_model=List[SocialRecommendation])
async def get_received_recommendations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    is_viewed: Optional[bool] = Query(None, description="Filter by viewed status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movie recommendations received from friends
    """
    try:
        social_service = SocialService(db)
        
        recommendations = social_service.get_received_recommendations(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            is_viewed=is_viewed
        )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error fetching received recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch received recommendations"
        )


@router.put("/recommendations/{recommendation_id}/view")
async def mark_recommendation_as_viewed(
    recommendation_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Mark a received recommendation as viewed
    """
    try:
        social_service = SocialService(db)
        
        # Check if recommendation exists and belongs to user
        recommendation = social_service.get_recommendation_by_id(recommendation_id)
        
        if not recommendation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found"
            )
        
        if recommendation.recipient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot mark another user's recommendation as viewed"
            )
        
        social_service.mark_recommendation_as_viewed(recommendation_id)
        
        return {"message": "Recommendation marked as viewed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking recommendation as viewed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark recommendation as viewed"
        )