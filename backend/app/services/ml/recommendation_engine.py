"""
Base recommendation engine interface
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import uuid

from app.schemas.movie import Movie


class RecommendationEngine(ABC):
    """Abstract base class for recommendation engines"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @abstractmethod
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[Movie]:
        """Get movie recommendations for a user"""
        pass
    
    @abstractmethod
    async def train_model(self) -> bool:
        """Train the recommendation model"""
        pass
    
    @abstractmethod
    async def get_explanation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get explanation for why a movie was recommended"""
        pass