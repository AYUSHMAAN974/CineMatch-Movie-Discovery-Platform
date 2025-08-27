"""
Collaborative filtering recommendation engine
"""
import pandas as pd
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Optional
import logging
import uuid
import pickle
import os

from app.services.ml.recommendation_engine import RecommendationEngine
from app.models.rating import Rating
from app.models.movie import Movie
from app.models.social import Friendship, FriendshipStatus
from app.schemas.movie import Movie as MovieSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class CollaborativeRecommender(RecommendationEngine):
    """Collaborative filtering recommendation engine"""
    
    def __init__(self, db):
        super().__init__(db)
        self.user_movie_matrix = None
        self.user_similarity_matrix = None
        self.movie_similarity_matrix = None
        self.svd_model = None
        self.user_index_map = {}
        self.movie_index_map = {}
        self.reverse_user_map = {}
        self.reverse_movie_map = {}
        
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[MovieSchema]:
        """Get collaborative filtering recommendations"""
        try:
            # Load or compute user-item matrix
            if self.user_movie_matrix is None:
                await self._load_or_compute_matrix()
            
            if str(user_id) not in self.user_index_map:
                logger.warning(f"User {user_id} not found in collaborative model")
                return await self._get_popular_movies(limit)
            
            user_idx = self.user_index_map[str(user_id)]
            
            # Get user's current ratings
            user_ratings = self.user_movie_matrix[user_idx].toarray().flatten()
            
            # Find similar users
            similar_users = await self._find_similar_users(user_idx)
            
            # Generate recommendations based on similar users
            recommendations = {}
            rated_movies = set(np.where(user_ratings > 0)[0])
            
            for similar_user_idx, similarity_score in similar_users[:50]:  # Top 50 similar users
                similar_user_ratings = self.user_movie_matrix[similar_user_idx].toarray().flatten()
                
                # Find highly rated movies by similar user
                for movie_idx, rating in enumerate(similar_user_ratings):
                    if rating >= 4.0 and movie_idx not in rated_movies:
                        movie_id = self.reverse_movie_map.get(movie_idx)
                        if movie_id:
                            if movie_id not in recommendations:
                                recommendations[movie_id] = 0
                            
                            # Weight by similarity and rating
                            recommendations[movie_id] += similarity_score * (rating / 5.0)
            
            # Sort by recommendation score
            sorted_recommendations = sorted(
                recommendations.items(),
                key=lambda x: x[1],
                reverse=True
            )[:limit]
            
            # Convert to MovieSchema
            movie_schemas = []
            for movie_id, score in sorted_recommendations:
                movie = self.db.query(Movie).filter(Movie.id == movie_id).first()
                if movie:
                    movie_schema = self._movie_to_schema(movie)
                    movie_schemas.append(movie_schema)
            
            return movie_schemas
            
        except Exception as e:
            logger.error(f"Error generating collaborative recommendations: {e}")
            return await self._get_popular_movies(limit)
    
    async def get_friend_based_recommendations(
        self,
        user_id: uuid.UUID,
        limit: int = 10
    ) -> List[MovieSchema]:
        """Get recommendations based on friends' ratings"""
        try:
            # Get user's friends
            friendships = self.db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == user_id, Friendship.status == FriendshipStatus.ACCEPTED.value),
                    and_(Friendship.friend_id == user_id, Friendship.status == FriendshipStatus.ACCEPTED.value)
                )
            ).all()
            
            friend_ids = []
            for friendship in friendships:
                if friendship.user_id == user_id:
                    friend_ids.append(friendship.friend_id)
                else:
                    friend_ids.append(friendship.user_id)
            
            if not friend_ids:
                return []
            
            # Get user's rated movies to exclude
            user_rated_movies = set()
            user_ratings = self.db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
            user_rated_movies = {rating.movie_id for rating in user_ratings}
            
            # Get friends' highly rated movies
            friend_recommendations = {}
            
            for friend_id in friend_ids:
                friend_ratings = self.db.query(Rating).join(Movie).filter(
                    Rating.user_id == friend_id,
                    Rating.rating >= 4.0,
                    ~Rating.movie_id.in_(user_rated_movies)
                ).all()
                
                for rating in friend_ratings:
                    movie_id = rating.movie_id
                    if movie_id not in friend_recommendations:
                        friend_recommendations[movie_id] = {
                            'total_score': 0,
                            'friend_count': 0,
                            'movie': rating.movie
                        }
                    
                    friend_recommendations[movie_id]['total_score'] += rating.rating
                    friend_recommendations[movie_id]['friend_count'] += 1
            
            # Calculate average scores and sort
            for movie_id in friend_recommendations:
                avg_score = (friend_recommendations[movie_id]['total_score'] / 
                           friend_recommendations[movie_id]['friend_count'])
                friend_recommendations[movie_id]['avg_score'] = avg_score
            
            # Sort by average score and friend count
            sorted_recommendations = sorted(
                friend_recommendations.items(),
                key=lambda x: (x[1]['avg_score'], x[1]['friend_count']),
                reverse=True
            )[:limit]
            
            # Convert to MovieSchema
            recommendations = []
            for movie_id, data in sorted_recommendations:
                movie = data['movie']
                movie_schema = self._movie_to_schema(movie)
                recommendations.append(movie_schema)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating friend-based recommendations: {e}")
            return []
    
    async def _load_or_compute_matrix(self):
        """Load existing user-item matrix or compute new one"""
        matrix_path = os.path.join(settings.ML_MODEL_PATH, "collaborative_matrix.pkl")
        
        try:
            if os.path.exists(matrix_path):
                with open(matrix_path, 'rb') as f:
                    data = pickle.load(f)
                    self.user_movie_matrix = data['user_movie_matrix']
                    self.user_index_map = data['user_index_map']
                    self.movie_index_map = data['movie_index_map']
                    self.reverse_user_map = data['reverse_user_map']
                    self.reverse_movie_map = data['reverse_movie_map']
                logger.info("Loaded existing collaborative filtering matrix")
            else:
                await self._compute_user_item_matrix()
                
        except Exception as e:
            logger.error(f"Error loading collaborative matrix: {e}")
            await self._compute_user_item_matrix()
    
    async def _compute_user_item_matrix(self):
        """Compute user-item rating matrix"""
        try:
            logger.info("Computing collaborative filtering matrix...")
            
            # Get all ratings
            ratings = self.db.query(Rating).all()
            
            if len(ratings) < 100:
                logger.warning("Not enough ratings for collaborative filtering")
                return
            
            # Create DataFrame
            ratings_data = []
            for rating in ratings:
                ratings_data.append({
                    'user_id': str(rating.user_id),
                    'movie_id': rating.movie_id,
                    'rating': rating.rating
                })
            
            df = pd.DataFrame(ratings_data)
            
            # Filter users and movies with minimum interactions
            user_counts = df['user_id'].value_counts()
            movie_counts = df['movie_id'].value_counts()
            
            # Keep users with at least 5 ratings and movies with at least 5 ratings
            active_users = user_counts[user_counts >= 5].index.tolist()
            active_movies = movie_counts[movie_counts >= 5].index.tolist()
            
            df_filtered = df[
                (df['user_id'].isin(active_users)) & 
                (df['movie_id'].isin(active_movies))
            ]
            
            if len(df_filtered) < 50:
                logger.warning("Not enough filtered ratings for collaborative filtering")
                return
            
            # Create user and movie index mappings
            unique_users = df_filtered['user_id'].unique()
            unique_movies = df_filtered['movie_id'].unique()
            
            self.user_index_map = {user: idx for idx, user in enumerate(unique_users)}
            self.movie_index_map = {movie: idx for idx, movie in enumerate(unique_movies)}
            self.reverse_user_map = {idx: user for user, idx in self.user_index_map.items()}
            self.reverse_movie_map = {idx: movie for movie, idx in self.movie_index_map.items()}
            
            # Create user-item matrix
            n_users = len(unique_users)
            n_movies = len(unique_movies)
            
            user_movie_matrix = np.zeros((n_users, n_movies))
            
            for _, row in df_filtered.iterrows():
                user_idx = self.user_index_map[row['user_id']]
                movie_idx = self.movie_index_map[row['movie_id']]
                user_movie_matrix[user_idx, movie_idx] = row['rating']
            
            # Convert to sparse matrix for efficiency
            self.user_movie_matrix = csr_matrix(user_movie_matrix)
            
            # Compute user similarity matrix
            self.user_similarity_matrix = cosine_similarity(self.user_movie_matrix)
            
            # Save to file
            os.makedirs(settings.ML_MODEL_PATH, exist_ok=True)
            
            with open(matrix_path, 'wb') as f:
                pickle.dump({
                    'user_movie_matrix': self.user_movie_matrix,
                    'user_index_map': self.user_index_map,
                    'movie_index_map': self.movie_index_map,
                    'reverse_user_map': self.reverse_user_map,
                    'reverse_movie_map': self.reverse_movie_map
                }, f)
            
            logger.info(f"Computed collaborative matrix: {n_users} users x {n_movies} movies")
            
        except Exception as e:
            logger.error(f"Error computing user-item matrix: {e}")
            raise
    
    async def _find_similar_users(self, user_idx: int, limit: int = 50) -> List[tuple]:
        """Find users similar to the given user"""
        try:
            if self.user_similarity_matrix is None:
                return []
            
            # Get similarity scores for the user
            user_similarities = self.user_similarity_matrix[user_idx]
            
            # Get indices of most similar users (excluding self)
            similar_user_indices = np.argsort(user_similarities)[::-1][1:limit+1]
            
            # Return user indices with similarity scores
            similar_users = [
                (idx, user_similarities[idx]) 
                for idx in similar_user_indices
                if user_similarities[idx] > 0.1  # Minimum similarity threshold
            ]
            
            return similar_users
            
        except Exception as e:
            logger.error(f"Error finding similar users: {e}")
            return []
    
    async def train_model(self) -> bool:
        """Train/retrain the collaborative filtering model"""
        try:
            await self._compute_user_item_matrix()
            return True
        except Exception as e:
            logger.error(f"Error training collaborative model: {e}")
            return False
    
    async def get_explanation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get explanation for collaborative filtering recommendation"""
        try:
            if str(user_id) not in self.user_index_map or movie_id not in self.movie_index_map:
                return None
            
            user_idx = self.user_index_map[str(user_id)]
            movie_idx = self.movie_index_map[movie_id]
            
            # Find similar users who rated this movie highly
            similar_users = await self._find_similar_users(user_idx, limit=20)
            
            similar_user_ratings = []
            for similar_user_idx, similarity_score in similar_users:
                rating = self.user_movie_matrix[similar_user_idx, movie_idx]
                if rating >= 4.0:
                    similar_user_ratings.append({
                        'similarity': round(similarity_score, 3),
                        'rating': rating
                    })
            
            if similar_user_ratings:
                avg_rating = np.mean([r['rating'] for r in similar_user_ratings])
                explanation = {
                    "type": "collaborative",
                    "reason": f"Users similar to you rated this movie {avg_rating:.1f}/5 on average",
                    "similar_users_count": len(similar_user_ratings),
                    "average_rating": round(avg_rating, 1)
                }
                return explanation
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating collaborative explanation: {e}")
            return None
    
    async def _get_popular_movies(self, limit: int) -> List[MovieSchema]:
        """Get popular movies as fallback"""
        try:
            movies = self.db.query(Movie).filter(
                Movie.is_active == True,
                Movie.vote_count >= 100
            ).order_by(Movie.popularity.desc()).limit(limit).all()
            
            return [self._movie_to_schema(movie) for movie in movies]
            
        except Exception as e:
            logger.error(f"Error getting popular movies: {e}")
            return []
    
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