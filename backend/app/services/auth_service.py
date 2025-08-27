"""
Authentication service for user management
"""
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import uuid

from app.core.security import security
from app.models.user import User, UserPreferences
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.auth import ChangePassword

logger = logging.getLogger(__name__)


class AuthService:
    """Service for handling authentication and user management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            return self.db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        except Exception as e:
            logger.error(f"Error fetching user by ID {user_id}: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        try:
            return self.db.query(User).filter(User.email == email).first()
        except Exception as e:
            logger.error(f"Error fetching user by email {email}: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        try:
            return self.db.query(User).filter(User.username == username).first()
        except Exception as e:
            logger.error(f"Error fetching user by username {username}: {e}")
            return None
    
    def create_user(self, user_create: UserCreate) -> User:
        """Create a new user account"""
        try:
            # Hash the password
            hashed_password = security.get_password_hash(user_create.password)
            
            # Create user instance
            db_user = User(
                email=user_create.email,
                username=user_create.username,
                hashed_password=hashed_password,
                full_name=user_create.full_name,
                is_active=True,
                is_verified=False
            )
            
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            
            # Create default user preferences
            self._create_default_preferences(db_user.id)
            
            logger.info(f"User created successfully: {db_user.email}")
            return db_user
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            self.db.rollback()
            raise
    
    def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """Update user information"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return None
            
            update_data = user_update.dict(exclude_unset=True)
            
            for field, value in update_data.items():
                if hasattr(user, field):
                    setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(user)
            
            logger.info(f"User updated successfully: {user.email}")
            return user
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            self.db.rollback()
            raise
    
    def update_password(self, user_id: str, new_password: str) -> bool:
        """Update user password"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            # Hash new password
            hashed_password = security.get_password_hash(new_password)
            user.hashed_password = hashed_password
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Password updated for user: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating password for user {user_id}: {e}")
            self.db.rollback()
            raise
    
    def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            user.last_login = datetime.utcnow()
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            self.db.rollback()
            return False
    
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            user.is_active = False
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"User deactivated: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            self.db.rollback()
            raise
    
    def verify_user(self, user_id: str) -> bool:
        """Verify user account"""
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            user.is_verified = True
            user.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"User verified: {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error verifying user {user_id}: {e}")
            self.db.rollback()
            raise
    
    def _create_default_preferences(self, user_id: uuid.UUID):
        """Create default preferences for new user"""
        try:
            preferences = UserPreferences(
                user_id=user_id,
                preferred_movie_length="any",
                share_ratings_publicly=True,
                allow_friend_recommendations=True,
                receive_notifications=True,
                prioritize_popular_movies=False,
                include_foreign_films=True,
                avoid_sequels=False
            )
            
            self.db.add(preferences)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating default preferences for user {user_id}: {e}")
            # Don't raise here as it shouldn't block user creation