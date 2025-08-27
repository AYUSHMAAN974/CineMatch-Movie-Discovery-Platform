"""
Hybrid recommendation engine combining multiple approaches
"""
from typing import List, Dict, Any, Optional
import logging
import uuid
import numpy as np
from datetime import datetime, timedelta

from app.services.ml.recommendation_engine import RecommendationEngine
from app.services.ml.content_based import ContentBasedRecommender
from app.services.ml.collaborative import CollaborativeRecommender
from app.services.ml.mood_analyzer import MoodAnalyzer
from app.schemas.movie import Movie as MovieSchema
from app.models.rating import Rating
from app.models.user import User

logger = logging.getLogger(__name__)


class HybridRecommender(RecommendationEngine):
    """Hybrid recommendation engine combining multiple approaches"""
    
    def __init__(self, db):
        super().__init__(db)
        self.content_recommender = ContentBasedRecommender(db)
        self.collaborative_recommender = CollaborativeRecommender(db)
        self.mood_analyzer = MoodAnalyzer(db)
        
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[MovieSchema]:
        """Get hybrid recommendations combining multiple approaches"""
        return await self.get_personal_recommendations(user_id, limit)
    
    async def get_personal_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10
    ) -> List[MovieSchema]:
        """Get personalized recommendations using hybrid approach"""
        try:
            # Get user's rating history to determine weights
            user_ratings_count = self.db.query(Rating).filter(
                Rating.user_id == user_id
            ).count()
            
            # Adjust weights based on user activity
            if user_ratings_count < 5:
                # New user - rely more on content and popularity
                content_weight = 0.6
                collaborative_weight = 0.1
                popularity_weight = 0.3
            elif user_ratings_count < 20:
                # Medium activity user
                content_weight = 0.5
                collaborative_weight = 0.3
                popularity_weight = 0.2
            else:
                # Active user - rely more on collaborative
                content_weight = 0.3
                collaborative_weight = 0.6
                popularity_weight = 0.1
            
            # Get recommendations from each system
            content_recs = await self.content_recommender.get_recommendations(
                user_id, limit=limit*2
            )
            
            collaborative_recs = await self.collaborative_recommender.get_recommendations(
                user_id, limit=limit*2
            )
            
            popular_recs = await self._get_trending_for_user(user_id, limit=limit)
            
            # Combine and score recommendations
            movie_scores = {}
            
            # Content-based recommendations
            for i, movie in enumerate(content_recs):
                score = content_weight * (1 - i / len(content_recs))
                movie_scores[movie.id] = movie_scores.get(movie.id, 0) + score
            
            # Collaborative recommendations
            for i, movie in enumerate(collaborative_recs):
                score = collaborative_weight * (1 - i / len(collaborative_recs))
                movie_scores[movie.id] = movie_scores.get(movie.id, 0) + score
            
            # Popular recommendations
            for i, movie in enumerate(popular_recs):
                score = popularity_weight * (1 - i / len(popular_recs))
                movie_scores[movie.id] = movie_scores.get(movie.id, 0) + score
            
            # Sort by combined score
            sorted_movies = sorted(movie_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Get movie objects and convert to schemas
            final_recommendations = []
            all_movies = {movie.id: movie for movie in content_recs + collaborative_recs + popular_recs}
            
            for movie_id, score in sorted_movies[:limit]:
                if movie_id in all_movies:
                    final_recommendations.append(all_movies[movie_id])
            
            return final_recommendations
            
        except Exception as e:
            logger.error(f"Error generating hybrid recommendations: {e}")
            # Fallback to content-based
            return await self.content_recommender.get_recommendations(user_id, limit)
    
    async def get_personalized_trending(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10
    ) -> List[MovieSchema]:
        """Get trending movies personalized for the user"""
        try:
            # Get user's preferred genres
            user_genre_preferences = await self._get_user_genre_preferences(user_id)
            
            # Get trending movies
            from app.services.tmdb.client import TMDBClient
            tmdb_client = TMDBClient()
            trending_movies = await tmdb_client.get_trending_movies("week")
            
            if not user_genre_preferences:
                return trending_movies[:limit]
            
            # Score trending movies based on user preferences
            scored_movies = []
            
            for movie in trending_movies:
                score = 0
                movie_obj = self.db.query(Movie).filter(Movie.id == movie.id).first()
                
                if movie_obj and movie_obj.genres:
                    for genre in movie_obj.genres:
                        if genre.name in user_genre_preferences:
                            score += user_genre_preferences[genre.name]
                
                scored_movies.append((movie, score))
            
            # Sort by personalized score
            scored_movies.sort(key=lambda x: x[1], reverse=True)
            
            return [movie for movie, score in scored_movies[:limit]]
            
        except Exception as e:
            logger.error(f"Error generating personalized trending: {e}")
            return []
    
    async def explain_recommendation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive explanation for recommendation"""
        try:
            explanations = []
            
            # Get explanations from different systems
            content_explanation = await self.content_recommender.get_explanation(user_id, movie_id)
            if content_explanation:
                explanations.append(content_explanation)
            
            collaborative_explanation = await self.collaborative_recommender.get_explanation(user_id, movie_id)
            if collaborative_explanation:
                explanations.append(collaborative_explanation)
            
            # Check if it's a trending movie
            trending_explanation = await self._check_trending_explanation(movie_id)
            if trending_explanation:
                explanations.append(trending_explanation)
            
            if not explanations:
                return None
            
            # Combine explanations
            primary_explanation = explanations[0]  # Use the first (usually strongest) explanation
            
            combined_explanation = {
                "primary_reason": primary_explanation["reason"],
                "explanation_type": primary_explanation["type"],
                "confidence_score": len(explanations) * 0.3,  # Higher confidence with more explanations
                "additional_factors": [exp["reason"] for exp in explanations[1:]] if len(explanations) > 1 else [],
                "recommendation_strength": self._calculate_recommendation_strength(explanations)
            }
            
            return combined_explanation
            
        except Exception as e:
            logger.error(f"Error generating hybrid explanation: {e}")
            return None
    
    async def train_model(self) -> bool:
        """Train all component models"""
        try:
            content_success = await self.content_recommender.train_model()
            collaborative_success = await self.collaborative_recommender.train_model()
            
            return content_success and collaborative_success
            
        except Exception as e:
            logger.error(f"Error training hybrid model: {e}")
            return False
    
    async def _get_trending_for_user(self, user_id: uuid.UUID, limit: int) -> List[MovieSchema]:
        """Get trending movies filtered by user preferences"""
        try:
            from app.services.tmdb.client import TMDBClient
            tmdb_client = TMDBClient()
            
            # Get general trending movies
            trending = await tmdb_client.get_trending_movies("day")
            popular = await tmdb_client.get_popular_movies()
            
            # Combine and deduplicate
            all_trending = []
            seen_ids = set()
            
            for movie in trending + popular:
                if movie.id not in seen_ids:
                    all_trending.append(movie)
                    seen_ids.add(movie.id)
            
            # Filter out movies user has already rated
            user_rated_movies = set()
            user_ratings = self.db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
            user_rated_movies = {rating.movie_id for rating in user_ratings}
            
            filtered_trending = [
                movie for movie in all_trending 
                if movie.id not in user_rated_movies
            ]
            
            return filtered_trending[:limit]
            
        except Exception as e:
            logger.error(f"Error getting trending for user: {e}")
            return []
    
    async def _get_user_genre_preferences(self, user_id: uuid.UUID) -> Dict[str, float]:
        """Get user's genre preferences based on ratings"""
        try:
            # Get user's ratings with movies and genres
            user_ratings = self.db.query(Rating).join(Movie).filter(
                Rating.user_id == user_id
            ).all()
            
            if not user_ratings:
                return {}
            
            genre_scores = {}
            genre_counts = {}
            
            for rating in user_ratings:
                if rating.movie and rating.movie.genres:
                    for genre in rating.movie.genres:
                        if genre.name not in genre_scores:
                            genre_scores[genre.name] = 0
                            genre_counts[genre.name] = 0
                        
                        genre_scores[genre.name] += rating.rating
                        genre_counts[genre.name] += 1
            
            # Calculate average scores
            genre_preferences = {}
            for genre, total_score in genre_scores.items():
                if genre_counts[genre] >= 2:  # At least 2 ratings
                    avg_score = total_score / genre_counts[genre]
                    # Normalize to preference score (-1 to 1)
                    preference = (avg_score - 2.5) / 2.5
                    genre_preferences[genre] = preference
            
            return genre_preferences
            
        except Exception as e:
            logger.error(f"Error getting user genre preferences: {e}")
            return {}
    
    async def _check_trending_explanation(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Check if movie is trending and provide explanation"""
        try:
            from app.services.tmdb.client import TMDBClient
            tmdb_client = TMDBClient()
            
            trending_today = await tmdb_client.get_trending_movies("day")
            trending_week = await tmdb_client.get_trending_movies("week")
            
            is_trending_today = any(movie.id == movie_id for movie in trending_today)
            is_trending_week = any(movie.id == movie_id for movie in trending_week)
            
            if is_trending_today:
                return {
                    "type": "trending",
                    "reason": "This movie is trending today",
                    "trending_period": "today"
                }
            elif is_trending_week:
                return {
                    "type": "trending",
                    "reason": "This movie is trending this week",
                    "trending_period": "week"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking trending explanation: {e}")
            return None
    
    def _calculate_recommendation_strength(self, explanations: List[Dict[str, Any]]) -> str:
        """Calculate overall recommendation strength"""
        if len(explanations) >= 3:
            return "very_high"
        elif len(explanations) == 2:
            return "high"
        elif len(explanations) == 1:
            return "medium"
        else:
            return "low"