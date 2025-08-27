"""
Mood-based recommendation engine
"""
from typing import List, Dict, Any, Optional
import logging
import uuid
from textblob import TextBlob
import re

from app.services.ml.recommendation_engine import RecommendationEngine
from app.models.movie import Movie, Genre
from app.models.rating import Rating, Review
from app.schemas.movie import Movie as MovieSchema
from app.core.config import settings

logger = logging.getLogger(__name__)


class MoodAnalyzer(RecommendationEngine):
    """Mood-based recommendation engine"""
    
    def __init__(self, db):
        super().__init__(db)
        self.mood_genre_mapping = {
            "happy": ["Comedy", "Family", "Animation", "Musical", "Romance"],
            "sad": ["Drama", "Romance"],
            "excited": ["Action", "Adventure", "Thriller", "Science Fiction"],
            "romantic": ["Romance", "Drama"],
            "adventurous": ["Adventure", "Action", "Fantasy", "Science Fiction"],
            "relaxed": ["Comedy", "Family", "Documentary"],
            "thoughtful": ["Drama", "Documentary", "Mystery", "Science Fiction"],
            "scared": ["Horror", "Thriller"],
            "nostalgic": ["Drama", "Family"],
            "energetic": ["Action", "Adventure", "Comedy"]
        }
        
        self.mood_keywords = {
            "happy": ["joy", "happiness", "cheerful", "uplifting", "positive", "fun", "lighthearted"],
            "sad": ["emotional", "touching", "tearjerker", "melancholy", "tragic", "heartbreaking"],
            "excited": ["thrilling", "intense", "adrenaline", "fast-paced", "explosive", "action-packed"],
            "romantic": ["love story", "romantic", "passion", "relationship", "intimate"],
            "adventurous": ["journey", "quest", "exploration", "epic", "adventure"],
            "relaxed": ["calm", "peaceful", "gentle", "easy-going", "comfort"],
            "thoughtful": ["philosophical", "deep", "complex", "intellectual", "thought-provoking"],
            "scared": ["scary", "frightening", "terrifying", "suspenseful", "creepy"],
            "nostalgic": ["classic", "vintage", "memories", "past", "childhood"],
            "energetic": ["dynamic", "vibrant", "energetic", "lively", "spirited"]
        }
    
    async def get_recommendations(
        self, 
        user_id: uuid.UUID, 
        limit: int = 10,
        exclude_watched: bool = True
    ) -> List[MovieSchema]:
        """Get mood-based recommendations (requires mood parameter)"""
        # This method requires a mood parameter, so we'll analyze user's recent activity
        recent_mood = await self._analyze_user_recent_mood(user_id)
        if recent_mood:
            return await self.get_mood_recommendations(user_id, recent_mood, limit)
        
        # Fallback to general recommendations
        return await self._get_popular_movies(limit)
    
    async def get_mood_recommendations(
        self,
        user_id: uuid.UUID,
        mood: str,
        limit: int = 10
    ) -> List[MovieSchema]:
        """Get recommendations based on specific mood"""
        try:
            if mood.lower() not in self.mood_genre_mapping:
                logger.warning(f"Unknown mood: {mood}")
                return []
            
            # Get genres for this mood
            target_genres = self.mood_genre_mapping[mood.lower()]
            
            # Get user's rated movies to exclude
            user_rated_movies = set()
            if user_id:
                user_ratings = self.db.query(Rating.movie_id).filter(Rating.user_id == user_id).all()
                user_rated_movies = {rating.movie_id for rating in user_ratings}
            
            # Query movies by genre
            movies_query = self.db.query(Movie).join(Movie.genres).filter(
                Genre.name.in_(target_genres),
                Movie.is_active == True,
                Movie.vote_count >= 20,
                ~Movie.id.in_(user_rated_movies) if user_rated_movies else True
            )
            
            # Get movies and score them by mood relevance
            movies = movies_query.all()
            
            if not movies:
                return []
            
            # Score movies by mood relevance
            scored_movies = []
            for movie in movies:
                mood_score = await self._calculate_mood_score(movie, mood.lower())
                scored_movies.append((movie, mood_score))
            
            # Sort by mood score and popularity
            # Sort by mood score and popularity
            scored_movies.sort(
                key=lambda x: (x[1], x[0].popularity or 0), 
                reverse=True
            )
            
            # Convert to schemas
            recommendations = []
            for movie, score in scored_movies[:limit]:
                movie_schema = self._movie_to_schema(movie)
                recommendations.append(movie_schema)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating mood recommendations for {mood}: {e}")
            return []
    
    async def _calculate_mood_score(self, movie: Movie, mood: str) -> float:
        """Calculate how well a movie matches a mood"""
        try:
            score = 0.0
            
            # Genre matching (base score)
            if movie.genres:
                movie_genres = [g.name for g in movie.genres]
                target_genres = self.mood_genre_mapping.get(mood, [])
                
                genre_matches = len(set(movie_genres) & set(target_genres))
                score += genre_matches * 0.3
            
            # Overview/tagline keyword matching
            text_content = ""
            if movie.overview:
                text_content += movie.overview.lower()
            if movie.tagline:
                text_content += " " + movie.tagline.lower()
            
            if text_content:
                mood_keywords = self.mood_keywords.get(mood, [])
                keyword_matches = sum(1 for keyword in mood_keywords if keyword in text_content)
                score += keyword_matches * 0.2
            
            # Review sentiment analysis (if available)
            review_sentiment_score = await self._get_review_sentiment_score(movie.id, mood)
            score += review_sentiment_score * 0.3
            
            # Rating and popularity boost
            if movie.vote_average:
                score += (movie.vote_average / 10.0) * 0.1
            
            if movie.popularity:
                # Normalize popularity (log scale)
                import math
                normalized_popularity = math.log(movie.popularity + 1) / 10.0
                score += min(normalized_popularity, 0.1)
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating mood score: {e}")
            return 0.0
    
    async def _get_review_sentiment_score(self, movie_id: int, mood: str) -> float:
        """Analyze review sentiments to match mood"""
        try:
            # Get recent reviews for this movie
            reviews = self.db.query(Review).filter(
                Review.movie_id == movie_id,
                Review.is_approved == True
            ).limit(10).all()
            
            if not reviews:
                return 0.0
            
            mood_score = 0.0
            review_count = 0
            
            for review in reviews:
                if not review.content:
                    continue
                
                # Simple sentiment analysis
                blob = TextBlob(review.content)
                sentiment_polarity = blob.sentiment.polarity  # -1 (negative) to 1 (positive)
                
                # Map sentiment to mood compatibility
                if mood in ["happy", "excited", "energetic"]:
                    mood_score += max(0, sentiment_polarity)
                elif mood in ["sad", "thoughtful"]:
                    mood_score += abs(sentiment_polarity)  # Both positive and negative emotions
                elif mood in ["scared"]:
                    mood_score += max(0, -sentiment_polarity) if sentiment_polarity < 0 else 0
                else:
                    mood_score += abs(sentiment_polarity) * 0.5
                
                review_count += 1
            
            return mood_score / review_count if review_count > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error analyzing review sentiment: {e}")
            return 0.0
    
    async def _analyze_user_recent_mood(self, user_id: uuid.UUID) -> Optional[str]:
        """Analyze user's recent activity to infer mood"""
        try:
            from datetime import datetime, timedelta
            
            # Get user's recent ratings (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_ratings = self.db.query(Rating).join(Movie).filter(
                Rating.user_id == user_id,
                Rating.created_at >= week_ago
            ).all()
            
            if not recent_ratings:
                return None
            
            # Analyze genres of recently rated movies
            genre_weights = {}
            total_ratings = 0
            
            for rating in recent_ratings:
                if rating.movie and rating.movie.genres:
                    weight = rating.rating / 5.0  # Higher rated movies have more influence
                    
                    for genre in rating.movie.genres:
                        if genre.name not in genre_weights:
                            genre_weights[genre.name] = 0
                        genre_weights[genre.name] += weight
                    
                    total_ratings += 1
            
            if not genre_weights:
                return None
            
            # Find most likely mood based on genre preferences
            mood_scores = {}
            for mood, target_genres in self.mood_genre_mapping.items():
                score = sum(genre_weights.get(genre, 0) for genre in target_genres)
                if score > 0:
                    mood_scores[mood] = score / total_ratings
            
            if mood_scores:
                # Return mood with highest score
                return max(mood_scores.items(), key=lambda x: x[1])[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing user recent mood: {e}")
            return None
    
    async def train_model(self) -> bool:
        """Train mood analysis model (analyze existing reviews)"""
        try:
            logger.info("Training mood analysis model...")
            
            # Get all approved reviews
            reviews = self.db.query(Review).filter(
                Review.is_approved == True,
                Review.content.isnot(None)
            ).all()
            
            if len(reviews) < 10:
                logger.warning("Not enough reviews for mood analysis training")
                return True  # Not critical, return success
            
            # Analyze sentiment for each review
            processed_count = 0
            
            for review in reviews:
                try:
                    # Skip if already analyzed
                    if review.sentiment_score is not None:
                        continue
                    
                    # Perform sentiment analysis
                    blob = TextBlob(review.content)
                    sentiment_score = blob.sentiment.polarity
                    
                    # Extract emotional tags
                    emotion_tags = self._extract_emotion_tags(review.content)
                    
                    # Update review
                    review.sentiment_score = sentiment_score
                    review.emotion_tags = ",".join(emotion_tags) if emotion_tags else None
                    
                    processed_count += 1
                    
                    if processed_count % 100 == 0:
                        self.db.commit()
                        logger.info(f"Processed {processed_count} reviews")
                
                except Exception as e:
                    logger.error(f"Error processing review {review.id}: {e}")
                    continue
            
            # Final commit
            self.db.commit()
            logger.info(f"Mood analysis training completed. Processed {processed_count} reviews")
            
            return True
            
        except Exception as e:
            logger.error(f"Error training mood analysis model: {e}")
            return False
    
    def _extract_emotion_tags(self, text: str) -> List[str]:
        """Extract emotion tags from text"""
        try:
            text_lower = text.lower()
            detected_emotions = []
            
            # Simple keyword-based emotion detection
            emotion_keywords = {
                "happy": ["happy", "joy", "delighted", "cheerful", "amazing", "wonderful", "fantastic", "great"],
                "sad": ["sad", "depressing", "tragic", "heartbreaking", "emotional", "touching", "tears"],
                "excited": ["exciting", "thrilling", "amazing", "incredible", "awesome", "spectacular"],
                "angry": ["angry", "frustrated", "annoying", "terrible", "awful", "hate"],
                "scared": ["scary", "frightening", "terrifying", "creepy", "horror", "fear"],
                "surprised": ["surprising", "unexpected", "twist", "shocking", "amazing"],
                "confused": ["confusing", "unclear", "complicated", "difficult", "strange"],
                "bored": ["boring", "slow", "tedious", "uninteresting", "dull"]
            }
            
            for emotion, keywords in emotion_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    detected_emotions.append(emotion)
            
            return detected_emotions
            
        except Exception as e:
            logger.error(f"Error extracting emotion tags: {e}")
            return []
    
    async def get_explanation(self, user_id: uuid.UUID, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get explanation for mood-based recommendation"""
        try:
            movie = self.db.query(Movie).filter(Movie.id == movie_id).first()
            if not movie:
                return None
            
            # Analyze what mood this movie matches
            mood_scores = {}
            for mood in self.mood_genre_mapping.keys():
                score = await self._calculate_mood_score(movie, mood)
                mood_scores[mood] = score
            
            best_mood = max(mood_scores.items(), key=lambda x: x[1])[0] if mood_scores else None
            
            if best_mood:
                explanation = {
                    "type": "mood_based",
                    "reason": f"Perfect for when you're feeling {best_mood}",
                    "detected_mood": best_mood,
                    "mood_score": round(mood_scores[best_mood], 2),
                    "matching_genres": [g.name for g in movie.genres 
                                      if g.name in self.mood_genre_mapping.get(best_mood, [])]
                }
                return explanation
            
            return None
            
        except Exception as e:
            logger.error(f"Error generating mood explanation: {e}")
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