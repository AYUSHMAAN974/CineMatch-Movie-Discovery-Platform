"""
Group recommendation engine for watch parties
"""
from typing import List, Dict, Any, Optional
import logging
import uuid
import numpy as np

from app.services.ml.recommendation_engine import RecommendationEngine
from app.models.rating import Rating
from app.models.movie import Movie, Genre
from app.schemas.movie import Movie as MovieSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class GroupRecommender(RecommendationEngine):
    """Group recommendation engine for finding movies that satisfy multiple users"""
    
    def __init__(self, db):
        super().__init__(db)
    
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[MovieSchema]:
        """Get group recommendations (requires multiple user IDs)"""
        return await self.get_group_recommendations([str(user_id)], limit)
    
    async def get_group_recommendations(
        self,
        user_ids: List[str],
        limit: int = 10,
        min_satisfaction: float = 0.6
    ) -> List[MovieSchema]:
        """Get recommendations that satisfy a group of users"""
        try:
            if len(user_ids) < 2:
                logger.warning("Group recommendations require at least 2 users")
                return []
            
            # Convert string IDs to UUID
            uuid_user_ids = []
            for user_id in user_ids:
                try:
                    uuid_user_ids.append(uuid.UUID(user_id))
                except ValueError:
                    logger.warning(f"Invalid user ID: {user_id}")
                    continue
            
            if len(uuid_user_ids) < 2:
                return []
            
            # Get all users' ratings
            all_user_ratings = {}
            all_rated_movies = set()
            
            for user_id in uuid_user_ids:
                user_ratings = self.db.query(Rating).filter(
                    Rating.user_id == user_id
                ).all()
                
                user_rating_dict = {rating.movie_id: rating.rating for rating in user_ratings}
                all_user_ratings[user_id] = user_rating_dict
                all_rated_movies.update(user_rating_dict.keys())
            
            # Find consensus candidates
            candidate_movies = await self._find_consensus_candidates(
                all_user_ratings, 
                uuid_user_ids,
                exclude_movies=all_rated_movies
            )
            
            # Score movies by group satisfaction
            scored_movies = []
            for movie in candidate_movies:
                satisfaction_score = await self._calculate_group_satisfaction(
                    movie, 
                    uuid_user_ids, 
                    all_user_ratings
                )
                
                if satisfaction_score >= min_satisfaction:
                    scored_movies.append((movie, satisfaction_score))
            
            # Sort by satisfaction score
            scored_movies.sort(key=lambda x: x[1], reverse=True)
            
            # Convert to schemas
            recommendations = []
            for movie, score in scored_movies[:limit]:
                movie_schema = self._movie_to_schema(movie)
                recommendations.append(movie_schema)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating group recommendations: {e}")
            return []
    
    async def _find_consensus_candidates(
        self,
        all_user_ratings: Dict[uuid.UUID, Dict[int, float]],
        user_ids: List[uuid.UUID],
        exclude_movies: set,
        candidate_limit: int = 200
    ) -> List[Movie]:
        """Find candidate movies based on user preferences"""
        try:
            # Analyze each user's genre preferences
            user_genre_preferences = {}
            
            for user_id in user_ids:
                user_ratings = all_user_ratings.get(user_id, {})
                genre_prefs = await self._get_user_genre_preferences(user_id, user_ratings)
                user_genre_preferences[user_id] = genre_prefs
            
            # Find common preferred genres
            common_genres = set()
            if user_genre_preferences:
                # Get genres that at least half the users like (rating >= 3.5)
                genre_support = {}
                
                for user_id, genre_prefs in user_genre_preferences.items():
                    for genre, avg_rating in genre_prefs.items():
                        if avg_rating >= 3.5:
                            if genre not in genre_support:
                                genre_support[genre] = 0
                            genre_support[genre] += 1
                
                min_support = len(user_ids) // 2 + 1  # At least half + 1
                common_genres = {
                    genre for genre, support in genre_support.items() 
                    if support >= min_support
                }
            
            # Get candidate movies from common genres
            if common_genres:
                candidates = self.db.query(Movie).join(Movie.genres).filter(
                    Genre.name.in_(common_genres),
                    Movie.is_active == True,
                    Movie.vote_count >= 50,
                    ~Movie.id.in_(exclude_movies) if exclude_movies else True
                ).order_by(Movie.popularity.desc()).limit(candidate_limit).all()
            else:
                # Fallback to popular movies
                candidates = self.db.query(Movie).filter(
                    Movie.is_active == True,
                    Movie.vote_count >= 100,
                    ~Movie.id.in_(exclude_movies) if exclude_movies else True
                ).order_by(Movie.popularity.desc()).limit(candidate_limit).all()
            
            return candidates
            
        except Exception as e:
            logger.error(f"Error finding consensus candidates: {e}")
            return []
    
    async def _calculate_group_satisfaction(
        self,
        movie: Movie,
        user_ids: List[uuid.UUID],
        all_user_ratings: Dict[uuid.UUID, Dict[int, float]]
    ) -> float:
        """Calculate how well a movie satisfies the group"""
        try:
            individual_satisfactions = []
            
            for user_id in user_ids:
                user_satisfaction = await self._predict_user_satisfaction(
                    movie, 
                    user_id, 
                    all_user_ratings.get(user_id, {})
                )
                individual_satisfactions.append(user_satisfaction)
            
            if not individual_satisfactions:
                return 0.0
            
            # Use different aggregation strategies
            mean_satisfaction = np.mean(individual_satisfactions)
            min_satisfaction = np.min(individual_satisfactions)
            
            # Weighted combination: ensure no user is completely unsatisfied
            # Give more weight to the minimum satisfaction to avoid completely unsatisfying anyone
            group_satisfaction = 0.6 * mean_satisfaction + 0.4 * min_satisfaction
            
            return max(0.0, min(1.0, group_satisfaction))
            
        except Exception as e:
            logger.error(f"Error calculating group satisfaction: {e}")
            return 0.0
    
    async def _predict_user_satisfaction(
        self,
        movie: Movie,
        user_id: uuid.UUID,
        user_ratings: Dict[int, float]
    ) -> float:
        """Predict how satisfied a user would be with this movie"""
        try:
            if not user_ratings:
                # New user - use movie popularity as proxy
                return (movie.vote_average or 5.0) / 10.0
            
            # Calculate satisfaction based on genre preferences
            user_genre_prefs = await self._get_user_genre_preferences(user_id, user_ratings)
            
            if not user_genre_prefs:
                return 0.5  # Neutral satisfaction
            
            # Score based on movie genres
            genre_satisfaction = 0.0
            genre_count = 0
            
            if movie.genres:
                for genre in movie.genres:
                    if genre.name in user_genre_prefs:
                        # Normalize rating to 0-1 scale
                        normalized_rating = (user_genre_prefs[genre.name] - 1) / 4.0
                        genre_satisfaction += max(0, normalized_rating)
                        genre_count += 1
                
                if genre_count > 0:
                    genre_satisfaction /= genre_count
            
            # Boost based on movie quality
            quality_boost = 0
            if movie.vote_average and movie.vote_average >= 7.0:
                quality_boost = 0.1
            
            # Penalty for very low ratings
            quality_penalty = 0
            if movie.vote_average and movie.vote_average < 5.0:
                quality_penalty = 0.2
            
            final_satisfaction = genre_satisfaction + quality_boost - quality_penalty
            return max(0.0, min(1.0, final_satisfaction))
            
        except Exception as e:
            logger.error(f"Error predicting user satisfaction: {e}")
            return 0.5
    
    async def _get_user_genre_preferences(
        self, 
        user_id: uuid.UUID, 
        user_ratings: Dict[int, float]
    ) -> Dict[str, float]:
        """Get user's genre preferences from their ratings"""
        try:
            if not user_ratings:
                return {}
            
            # Get movies and their genres for rated movies
            movie_ids = list(user_ratings.keys())
            movies = self.db.query(Movie).filter(Movie.id.in_(movie_ids)).all()
            
            genre_scores = {}
            genre_counts = {}
            
            for movie in movies:
                if movie.id in user_ratings and movie.genres:
                    rating = user_ratings[movie.id]
                    
                    for genre in movie.genres:
                        if genre.name not in genre_scores:
                            genre_scores[genre.name] = 0
                            genre_counts[genre.name] = 0
                        
                        genre_scores[genre.name] += rating
                        genre_counts[genre.name] += 1
            
            # Calculate average ratings per genre
            genre_preferences = {}
            for genre, total_score in genre_scores.items():
                if genre_counts[genre] >= 2:  # At least 2 ratings
                    genre_preferences[genre] = total_score / genre_counts[genre]
            
            return genre_preferences
            
        except Exception as e:
            logger.error(f"Error getting user genre preferences: {e}")
            return {}
    
    async def train_model(self) -> bool:
        """Group recommender doesn't need specific training"""
        return True
    
    async def get_explanation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get explanation for group recommendation"""
        try:
            movie = self.db.query(Movie).filter(Movie.id == movie_id).first()
            if not movie:
                return None
            
            explanation = {
                "type": "group_consensus",
                "reason": "This movie balances everyone's preferences",
                "consensus_factors": {
                    "shared_genres": [g.name for g in movie.genres] if movie.genres else [],
                    "quality_rating": movie.vote_average,
                    "popularity": "high" if movie.popularity and movie.popularity > 50 else "moderate"
                }
            }
            
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating group explanation: {e}")
            return None
    
    def _movie_to_schema(self, movie: Movie) -> MovieSchema:
        """Convert Movie model to MovieSchema"""
        return MovieSchema(
            id=movie.id,
            title=movie.title,
            original_title=movie.original_title,
            overview=movie.overview,
            release_date=movie.release_date,
            poster_path=movie.poster_path,
            backdrop_path=movie.backdrop_path,
            adult=movie.adult,
            original_language=movie.original_language,
            popularity=movie.popularity,
            vote_average=movie.vote_average,
            vote_count=movie.vote_count,
            poster_url=f"{settings.TMDB_IMAGE_BASE_URL}/w500{movie.poster_path}" 
                      if movie.poster_path else None,
            backdrop_url=f"{settings.TMDB_IMAGE_BASE_URL}/w1280{movie.backdrop_path}" 
                        if movie.backdrop_path else None,
            year=movie.release_date.year if movie.release_date else None,
            created_at=movie.created_at or datetime.utcnow()
        )