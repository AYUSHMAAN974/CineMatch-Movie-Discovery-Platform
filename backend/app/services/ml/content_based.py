"""
Content-based recommendation engine
"""
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Any, Optional
import logging
import uuid
import pickle
import os

from app.services.ml.recommendation_engine import RecommendationEngine
from app.models.movie import Movie, Genre
from app.models.rating import Rating
from app.schemas.movie import Movie as MovieSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class ContentBasedRecommender(RecommendationEngine):
    """Content-based recommendation engine using movie features"""
    
    def __init__(self, db):
        super().__init__(db)
        self.similarity_matrix = None
        self.movie_features = None
        self.movie_indices = None
        self.scaler = StandardScaler()
        self.tfidf_vectorizer = TfidfVectorizer(max_features=5000, stop_words='english')
        
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[MovieSchema]:
        """Get content-based recommendations for a user"""
        try:
            # Get user's highly rated movies (>= 4.0)
            user_ratings = self.db.query(Rating).filter(
                Rating.user_id == user_id,
                Rating.rating >= 4.0
            ).all()
            
            if not user_ratings:
                # Return popular movies if no ratings
                return await self._get_popular_movies(limit)
            
            # Get movie IDs user has rated (to exclude)
            rated_movie_ids = {rating.movie_id for rating in user_ratings} if exclude_watched else set()
            
            # Get similar movies for each highly rated movie
            candidate_movies = {}
            
            for rating in user_ratings:
                similar_movies = await self._get_similar_movies_internal(
                    rating.movie_id, 
                    limit=20,
                    exclude_ids=rated_movie_ids
                )
                
                # Weight by user's rating
                weight = rating.rating / 5.0
                
                for movie, similarity_score in similar_movies:
                    if movie.id not in candidate_movies:
                        candidate_movies[movie.id] = {
                            'movie': movie,
                            'score': 0.0,
                            'count': 0
                        }
                    
                    candidate_movies[movie.id]['score'] += similarity_score * weight
                    candidate_movies[movie.id]['count'] += 1
            
            # Sort by weighted score
            sorted_candidates = sorted(
                candidate_movies.values(),
                key=lambda x: x['score'] / x['count'],  # Average weighted score
                reverse=True
            )
            
            # Convert to MovieSchema and return top recommendations
            recommendations = []
            for candidate in sorted_candidates[:limit]:
                movie = candidate['movie']
                movie_schema = self._movie_to_schema(movie)
                recommendations.append(movie_schema)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating content-based recommendations: {e}")
            return await self._get_popular_movies(limit)
    
    async def get_similar_movies(
        self,
        movie_id: int,
        user_id: Optional[uuid.UUID] = None,
        limit: int = 10
    ) -> List[MovieSchema]:
        """Get movies similar to a specific movie"""
        try:
            # Get movies to exclude if user provided
            exclude_ids = set()
            if user_id:
                user_ratings = self.db.query(Rating.movie_id).filter(
                    Rating.user_id == user_id
                ).all()
                exclude_ids = {rating.movie_id for rating in user_ratings}
            
            similar_movies = await self._get_similar_movies_internal(
                movie_id,
                limit=limit,
                exclude_ids=exclude_ids
            )
            
            return [self._movie_to_schema(movie) for movie, _ in similar_movies]
            
        except Exception as e:
            logger.error(f"Error getting similar movies for {movie_id}: {e}")
            return []
    
    async def _get_similar_movies_internal(
        self,
        movie_id: int,
        limit: int = 10,
        exclude_ids: set = None
    ) -> List[tuple]:
        """Internal method to get similar movies"""
        try:
            if exclude_ids is None:
                exclude_ids = set()
            
            # Load similarity matrix if not loaded
            if self.similarity_matrix is None:
                await self._load_or_compute_similarity_matrix()
            
            # Get movie index
            if movie_id not in self.movie_indices:
                logger.warning(f"Movie {movie_id} not found in similarity matrix")
                return []
            
            movie_idx = self.movie_indices[movie_id]
            
            # Get similarity scores
            sim_scores = list(enumerate(self.similarity_matrix[movie_idx]))
            
            # Sort by similarity (excluding the movie itself)
            sim_scores = [score for score in sim_scores if score[0] != movie_idx]
            sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
            
            # Get similar movies
            similar_movies = []
            for idx, score in sim_scores:
                if len(similar_movies) >= limit:
                    break
                
                similar_movie_id = list(self.movie_indices.keys())[
                    list(self.movie_indices.values()).index(idx)
                ]
                
                if similar_movie_id in exclude_ids:
                    continue
                
                movie = self.db.query(Movie).filter(Movie.id == similar_movie_id).first()
                if movie:
                    similar_movies.append((movie, score))
            
            return similar_movies
            
        except Exception as e:
            logger.error(f"Error getting similar movies internally: {e}")
            return []
    
    async def _load_or_compute_similarity_matrix(self):
        """Load existing similarity matrix or compute new one"""
        matrix_path = os.path.join(settings.ML_MODEL_PATH, "content_similarity_matrix.pkl")
        
        try:
            # Try to load existing matrix
            if os.path.exists(matrix_path):
                with open(matrix_path, 'rb') as f:
                    data = pickle.load(f)
                    self.similarity_matrix = data['similarity_matrix']
                    self.movie_indices = data['movie_indices']
                    self.movie_features = data['movie_features']
                logger.info("Loaded existing similarity matrix")
            else:
                # Compute new matrix
                await self._compute_similarity_matrix()
                
        except Exception as e:
            logger.error(f"Error loading similarity matrix: {e}")
            await self._compute_similarity_matrix()
    
    async def _compute_similarity_matrix(self):
        """Compute movie similarity matrix"""
        try:
            logger.info("Computing content-based similarity matrix...")
            
            # Get all active movies with sufficient data
            movies = self.db.query(Movie).filter(
                Movie.is_active == True,
                Movie.overview.isnot(None),
                Movie.vote_count >= 10
            ).all()
            
            if len(movies) < 10:
                logger.warning("Not enough movies to compute similarity matrix")
                return
            
            # Extract features
            movie_data = []
            for movie in movies:
                # Text features
                overview = movie.overview or ""
                tagline = movie.tagline or ""
                text_content = f"{overview} {tagline}"
                
                # Categorical features
                genres = [g.name for g in movie.genres] if movie.genres else []
                genre_str = " ".join(genres)
                
                # Combine text features
                combined_text = f"{text_content} {genre_str}"
                
                movie_data.append({
                    'id': movie.id,
                    'text_content': combined_text,
                    'vote_average': movie.vote_average or 0,
                    'popularity': movie.popularity or 0,
                    'runtime': movie.runtime or 0,
                    'release_year': movie.release_date.year if movie.release_date else 0
                })
            
            # Create DataFrame
            df = pd.DataFrame(movie_data)
            
            # TF-IDF for text features
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(df['text_content'])
            
            # Numerical features
            numerical_features = ['vote_average', 'popularity', 'runtime', 'release_year']
            numerical_data = df[numerical_features].fillna(0)
            scaled_numerical = self.scaler.fit_transform(numerical_data)
            
            # Combine features
            # Give more weight to text features (0.7) vs numerical (0.3)
            text_similarity = cosine_similarity(tfidf_matrix)
            numerical_similarity = cosine_similarity(scaled_numerical)
            
            # Weighted combination
            self.similarity_matrix = 0.7 * text_similarity + 0.3 * numerical_similarity
            
            # Create movie index mapping
            self.movie_indices = {movie_id: idx for idx, movie_id in enumerate(df['id'])}
            self.movie_features = df
            
            # Save to file
            os.makedirs(settings.ML_MODEL_PATH, exist_ok=True)
            matrix_path = os.path.join(settings.ML_MODEL_PATH, "content_similarity_matrix.pkl")
            
            with open(matrix_path, 'wb') as f:
                pickle.dump({
                    'similarity_matrix': self.similarity_matrix,
                    'movie_indices': self.movie_indices,
                    'movie_features': self.movie_features
                }, f)
            
            logger.info(f"Computed similarity matrix for {len(movies)} movies")
            
        except Exception as e:
            logger.error(f"Error computing similarity matrix: {e}")
            raise
    
    async def train_model(self) -> bool:
        """Train/retrain the content-based model"""
        try:
            await self._compute_similarity_matrix()
            return True
        except Exception as e:
            logger.error(f"Error training content-based model: {e}")
            return False
    
    async def get_explanation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get explanation for why a movie was recommended"""
        try:
            # Get user's top-rated movies
            top_rated = self.db.query(Rating).join(Movie).filter(
                Rating.user_id == user_id,
                Rating.rating >= 4.0
            ).order_by(Rating.rating.desc()).limit(3).all()
            
            if not top_rated:
                return None
            
            # Get the recommended movie
            recommended_movie = self.db.query(Movie).filter(Movie.id == movie_id).first()
            if not recommended_movie:
                return None
            
            # Find most similar movie from user's top rated
            max_similarity = 0
            most_similar_movie = None
            
            for rating in top_rated:
                similar_movies = await self._get_similar_movies_internal(
                    rating.movie_id,
                    limit=50,
                    exclude_ids=set()
                )
                
                for movie, similarity_score in similar_movies:
                    if movie.id == movie_id and similarity_score > max_similarity:
                        max_similarity = similarity_score
                        most_similar_movie = rating.movie
            
            if most_similar_movie:
                # Find common features
                common_genres = set(g.name for g in recommended_movie.genres) & set(g.name for g in most_similar_movie.genres)
                
                explanation = {
                    "type": "content_based",
                    "reason": f"Similar to '{most_similar_movie.title}' which you rated {rating.rating}/5",
                    "similarity_score": round(max_similarity, 3),
                    "common_features": {
                        "genres": list(common_genres),
                        "similar_themes": self._extract_theme_similarities(
                            most_similar_movie.overview or "",
                            recommended_movie.overview or ""
                        )
                    }
                }
                return explanation
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return None
    
    def _extract_theme_similarities(self, text1: str, text2: str) -> List[str]:
        """Extract common themes between two movie descriptions"""
        # Simple keyword matching for themes
        themes = {
            "action": ["action", "fight", "battle", "war", "combat"],
            "romance": ["love", "romance", "relationship", "romantic"],
            "adventure": ["adventure", "journey", "quest", "explore"],
            "mystery": ["mystery", "detective", "investigation", "secret"],
            "family": ["family", "children", "parent", "home"],
            "friendship": ["friend", "friendship", "companion", "buddy"]
        }
        
        text1_lower = text1.lower()
        text2_lower = text2.lower()
        
        common_themes = []
        for theme, keywords in themes.items():
            if any(keyword in text1_lower for keyword in keywords) and \
               any(keyword in text2_lower for keyword in keywords):
                common_themes.append(theme)
        
        return common_themes
    
    async def _get_popular_movies(self, limit: int) -> List[MovieSchema]:
        """Get popular movies as fallback recommendations"""
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