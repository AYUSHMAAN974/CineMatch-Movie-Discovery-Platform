"""
Service for handling social features
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func, and_, or_
from datetime import datetime
import logging
import uuid
import secrets
import string

from app.models.social import (
    Friendship, WatchParty, WatchPartyMember, WatchPartyMovieSuggestion,
    SocialRecommendation, FriendshipStatus
)
from app.models.user import User
from app.models.movie import Movie
from app.schemas.social import (
    FriendshipCreate, WatchPartyCreate, WatchPartyList,
    SocialRecommendationCreate
)

logger = logging.getLogger(__name__)


class SocialService:
    """Service for handling social features"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Friendship methods
    def send_friend_request(self, user_id: uuid.UUID, friend_request: FriendshipCreate) -> Friendship:
        """Send a friend request"""
        try:
            # Get friend by username
            friend = self.db.query(User).filter(
                User.username == friend_request.friend_username
            ).first()
            
            if not friend:
                raise ValueError("User not found")
            
            # Create friendship request
            friendship = Friendship(
                user_id=user_id,
                friend_id=friend.id,
                status=FriendshipStatus.PENDING.value,
                message=friend_request.message
            )
            
            self.db.add(friendship)
            self.db.commit()
            self.db.refresh(friendship)
            
            logger.info(f"Friend request sent from {user_id} to {friend.id}")
            return friendship
            
        except Exception as e:
            logger.error(f"Error sending friend request: {e}")
            self.db.rollback()
            raise
    
    def get_friendship_by_id(self, friendship_id: str) -> Optional[Friendship]:
        """Get friendship by ID"""
        try:
            return self.db.query(Friendship).filter(
                Friendship.id == uuid.UUID(friendship_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching friendship {friendship_id}: {e}")
            return None
    
    def get_friendship_status(self, user_id: uuid.UUID, friend_username: str) -> Optional[str]:
        """Get friendship status between two users"""
        try:
            friend = self.db.query(User).filter(
                User.username == friend_username
            ).first()
            
            if not friend:
                return None
            
            # Check both directions
            friendship = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == user_id, Friendship.friend_id == friend.id),
                    and_(Friendship.user_id == friend.id, Friendship.friend_id == user_id)
                )
            ).first()
            
            return friendship.status if friendship else None
            
        except Exception as e:
            logger.error(f"Error getting friendship status: {e}")
            return None
    
    def update_friendship_status(self, friendship_id: str, status: str) -> Friendship:
        """Update friendship status (accept, decline, block)"""
        try:
            friendship = self.get_friendship_by_id(friendship_id)
            if not friendship:
                raise ValueError("Friendship not found")
            
            friendship.status = status
            friendship.updated_at = datetime.utcnow()
            
            if status == FriendshipStatus.ACCEPTED.value:
                friendship.accepted_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(friendship)
            
            logger.info(f"Friendship {friendship_id} status updated to {status}")
            return friendship
            
        except Exception as e:
            logger.error(f"Error updating friendship status: {e}")
            self.db.rollback()
            raise
    
    def get_user_friendships(
        self, 
        user_id: uuid.UUID, 
        status: Optional[str] = None
    ) -> List[Friendship]:
        """Get user's friendships"""
        try:
            query = self.db.query(Friendship).options(
                joinedload(Friendship.user),
                joinedload(Friendship.friend)
            ).filter(
                or_(Friendship.user_id == user_id, Friendship.friend_id == user_id)
            )
            
            if status:
                query = query.filter(Friendship.status == status)
            
            friendships = query.order_by(desc(Friendship.created_at)).all()
            
            return friendships
            
        except Exception as e:
            logger.error(f"Error fetching user friendships: {e}")
            return []
    
    def are_friends(self, user_id: uuid.UUID, friend_id: uuid.UUID) -> bool:
        """Check if two users are friends"""
        try:
            friendship = self.db.query(Friendship).filter(
                or_(
                    and_(
                        Friendship.user_id == user_id, 
                        Friendship.friend_id == friend_id,
                        Friendship.status == FriendshipStatus.ACCEPTED.value
                    ),
                    and_(
                        Friendship.user_id == friend_id, 
                        Friendship.friend_id == user_id,
                        Friendship.status == FriendshipStatus.ACCEPTED.value
                    )
                )
            ).first()
            
            return friendship is not None
            
        except Exception as e:
            logger.error(f"Error checking friendship: {e}")
            return False
    
    # Watch Party methods
    def create_watch_party(self, creator_id: uuid.UUID, party_data: WatchPartyCreate) -> WatchParty:
        """Create a new watch party"""
        try:
            # Generate invitation code
            invitation_code = self._generate_invitation_code()
            
            watch_party = WatchParty(
                creator_id=creator_id,
                name=party_data.name,
                description=party_data.description,
                movie_id=party_data.movie_id,
                scheduled_time=party_data.scheduled_time,
                duration_minutes=party_data.duration_minutes,
                is_public=party_data.is_public,
                max_participants=party_data.max_participants,
                allow_movie_suggestions=party_data.allow_movie_suggestions,
                require_approval=party_data.require_approval,
                invitation_code=invitation_code
            )
            
            self.db.add(watch_party)
            self.db.commit()
            self.db.refresh(watch_party)
            
            # Add creator as member
            creator_membership = WatchPartyMember(
                watch_party_id=watch_party.id,
                user_id=creator_id,
                status="accepted",
                role="admin",
                joined_at=datetime.utcnow()
            )
            
            self.db.add(creator_membership)
            self.db.commit()
            
            logger.info(f"Watch party created: {watch_party.id} by {creator_id}")
            return watch_party
            
        except Exception as e:
            logger.error(f"Error creating watch party: {e}")
            self.db.rollback()
            raise
    
    def get_watch_party_by_id(self, party_id: str) -> Optional[WatchParty]:
        """Get watch party by ID"""
        try:
            return self.db.query(WatchParty).options(
                joinedload(WatchParty.creator),
                joinedload(WatchParty.members),
                joinedload(WatchParty.movie_suggestions)
            ).filter(WatchParty.id == uuid.UUID(party_id)).first()
        except Exception as e:
            logger.error(f"Error fetching watch party {party_id}: {e}")
            return None
    
    def get_user_watch_parties(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None
    ) -> WatchPartyList:
        """Get user's watch parties"""
        try:
            # Query for parties where user is creator or member
            query = self.db.query(WatchParty).join(
                WatchPartyMember,
                WatchParty.id == WatchPartyMember.watch_party_id
            ).filter(
                or_(
                    WatchParty.creator_id == user_id,
                    and_(
                        WatchPartyMember.user_id == user_id,
                        WatchPartyMember.status == "accepted"
                    )
                )
            ).distinct()
            
            if status:
                query = query.filter(WatchParty.status == status)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            parties = query.order_by(desc(WatchParty.created_at)).offset(offset).limit(page_size).all()
            
            return WatchPartyList(
                watch_parties=parties,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
                has_next=page * page_size < total,
                has_prev=page > 1
            )
            
        except Exception as e:
            logger.error(f"Error fetching user watch parties: {e}")
            raise
    
    def is_party_member(self, party_id: str, user_id: uuid.UUID) -> bool:
        """Check if user is a member of watch party"""
        try:
            membership = self.db.query(WatchPartyMember).filter(
                and_(
                    WatchPartyMember.watch_party_id == uuid.UUID(party_id),
                    WatchPartyMember.user_id == user_id,
                    WatchPartyMember.status.in_(["accepted", "invited"])
                )
            ).first()
            
            return membership is not None
            
        except Exception as e:
            logger.error(f"Error checking party membership: {e}")
            return False
    
    def join_watch_party(self, party_id: str, user_id: uuid.UUID) -> WatchPartyMember:
        """Join a watch party"""
        try:
            membership = WatchPartyMember(
                watch_party_id=uuid.UUID(party_id),
                user_id=user_id,
                status="accepted",  # Could be "invited" if approval required
                role="member",
                joined_at=datetime.utcnow()
            )
            
            self.db.add(membership)
            self.db.commit()
            self.db.refresh(membership)
            
            logger.info(f"User {user_id} joined watch party {party_id}")
            return membership
            
        except Exception as e:
            logger.error(f"Error joining watch party: {e}")
            self.db.rollback()
            raise
    
    # Social Recommendation methods
    def send_movie_recommendation(
        self, 
        sender_id: uuid.UUID, 
        recommendation_data: SocialRecommendationCreate
    ) -> SocialRecommendation:
        """Send a movie recommendation to a friend"""
        try:
            recommendation = SocialRecommendation(
                sender_id=sender_id,
                recipient_id=recommendation_data.recipient_id,
                movie_id=recommendation_data.movie_id,
                message=recommendation_data.message,
                rating=recommendation_data.rating,
                confidence=recommendation_data.confidence
            )
            
            self.db.add(recommendation)
            self.db.commit()
            self.db.refresh(recommendation)
            
            logger.info(f"Movie recommendation sent from {sender_id} to {recommendation_data.recipient_id}")
            return recommendation
            
        except Exception as e:
            logger.error(f"Error sending movie recommendation: {e}")
            self.db.rollback()
            raise
    
    def get_recommendation_by_id(self, recommendation_id: str) -> Optional[SocialRecommendation]:
        """Get recommendation by ID"""
        try:
            return self.db.query(SocialRecommendation).filter(
                SocialRecommendation.id == uuid.UUID(recommendation_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching recommendation {recommendation_id}: {e}")
            return None
    
    def get_received_recommendations(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        is_viewed: Optional[bool] = None
    ) -> List[SocialRecommendation]:
        """Get recommendations received by user"""
        try:
            query = self.db.query(SocialRecommendation).options(
                joinedload(SocialRecommendation.sender),
                joinedload(SocialRecommendation.movie)
            ).filter(SocialRecommendation.recipient_id == user_id)
            
            if is_viewed is not None:
                query = query.filter(SocialRecommendation.is_viewed == is_viewed)
            
            offset = (page - 1) * page_size
            recommendations = query.order_by(desc(SocialRecommendation.created_at)).offset(offset).limit(page_size).all()
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error fetching received recommendations: {e}")
            return []
    
    def mark_recommendation_as_viewed(self, recommendation_id: str):
        """Mark a recommendation as viewed"""
        try:
            recommendation = self.get_recommendation_by_id(recommendation_id)
            if recommendation:
                recommendation.is_viewed = True
                recommendation.viewed_at = datetime.utcnow()
                self.db.commit()
                
        except Exception as e:
            logger.error(f"Error marking recommendation as viewed: {e}")
            self.db.rollback()
            raise
    
    def _generate_invitation_code(self, length: int = 8) -> str:
        """Generate a random invitation code for watch parties"""
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))