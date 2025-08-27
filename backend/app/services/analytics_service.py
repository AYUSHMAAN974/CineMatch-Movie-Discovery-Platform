"""
Service for user analytics and insights
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, and_, or_
from datetime import datetime, timedelta
import logging
import uuid

from app.models.user import User, UserActivity
from app.models.rating import Rating, Review
from app.models.movie import Movie, Genre
from app.schemas.analytics import (
    UserTasteProfile, ViewingPatterns, UserStats,
    MovieTrendAnalysis, RecommendationPerformance
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for handling analytics and user insights"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_taste_profile(self, user_id: uuid.UUID) -> UserTasteProfile:
        """Get detailed analysis of user's movie taste and preferences"""
        try:
            # Get user's ratings
            ratings = self.db.query(Rating).join(Movie).filter(
                Rating.user_id == user_id
            ).all()
            
            if not ratings:
                return UserTasteProfile(user_id=user_id)
            
            # Genre preferences
            genre_ratings = {}
            genre_counts = {}
            
            for rating in ratings:
                movie = rating.movie
                if movie and movie.genres:
                    for genre in movie.genres:
                        if genre.name not in genre_ratings:
                            genre_ratings[genre.name] = []
                            genre_counts[genre.name] = 0
                        
                        genre_ratings[genre.name].append(rating.rating)
                        genre_counts[genre.name] += 1
            
            # Calculate average ratings per genre
            genre_preferences = {}
            for genre, ratings_list in genre_ratings.items():
                avg_rating = sum(ratings_list) / len(ratings_list)
                genre_preferences[genre] = {
                    "average_rating": round(avg_rating, 2),
                    "count": genre_counts[genre],
                    "preference_score": round((avg_rating - 2.5) * 40, 1)  # Scale to -100 to 100
                }
            
            # Decade preferences
            decade_preferences = self._calculate_decade_preferences(ratings)
            
            # Language preferences
            language_preferences = self._calculate_language_preferences(ratings)
            
            # Runtime preferences
            runtime_preferences = self._calculate_runtime_preferences(ratings)
            
            # Mood preferences (based on genres and ratings)
            mood_preferences = self._calculate_mood_preferences(genre_preferences)
            
            return UserTasteProfile(
                user_id=user_id,
                genre_preferences=genre_preferences,
                decade_preferences=decade_preferences,
                language_preferences=language_preferences,
                runtime_preferences=runtime_preferences,
                mood_preferences=mood_preferences,
                total_ratings=len(ratings),
                average_rating=round(sum(r.rating for r in ratings) / len(ratings), 2),
                rating_variance=self._calculate_rating_variance(ratings),
                diversity_score=self._calculate_diversity_score(ratings),
                last_updated=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error calculating taste profile for user {user_id}: {e}")
            return UserTasteProfile(user_id=user_id)
    
    def get_viewing_patterns(self, user_id: uuid.UUID, days: int = 30) -> ViewingPatterns:
        """Get user's viewing patterns and behavior analysis"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get user activities in the time range
            activities = self.db.query(UserActivity).filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= start_date
                )
            ).all()
            
            # Activity by hour of day
            hourly_activity = {str(hour): 0 for hour in range(24)}
            
            # Activity by day of week
            daily_activity = {str(day): 0 for day in range(7)}  # 0 = Monday
            
            # Activity types
            activity_types = {}
            
            for activity in activities:
                hour = activity.created_at.hour
                day = activity.created_at.weekday()
                activity_type = activity.activity_type
                
                hourly_activity[str(hour)] += 1
                daily_activity[str(day)] += 1
                
                if activity_type not in activity_types:
                    activity_types[activity_type] = 0
                activity_types[activity_type] += 1
            
            # Peak activity times
            peak_hour = max(hourly_activity, key=hourly_activity.get)
            peak_day = max(daily_activity, key=daily_activity.get)
            
            # Rating patterns (time between ratings)
            ratings = self.db.query(Rating).filter(
                and_(
                    Rating.user_id == user_id,
                    Rating.created_at >= start_date
                )
            ).order_by(Rating.created_at).all()
            
            rating_intervals = []
            if len(ratings) > 1:
                for i in range(1, len(ratings)):
                    interval = (ratings[i].created_at - ratings[i-1].created_at).total_seconds() / 3600  # hours
                    rating_intervals.append(interval)
            
            avg_rating_interval = sum(rating_intervals) / len(rating_intervals) if rating_intervals else 0
            
            return ViewingPatterns(
                user_id=user_id,
                analysis_period_days=days,
                total_activities=len(activities),
                hourly_activity=hourly_activity,
                daily_activity=daily_activity,
                activity_types=activity_types,
                peak_activity_hour=int(peak_hour),
                peak_activity_day=int(peak_day),
                average_rating_interval_hours=round(avg_rating_interval, 2),
                most_active_day_name=self._get_day_name(int(peak_day)),
                total_ratings_period=len(ratings),
                binge_watching_score=self._calculate_binge_score(activities)
            )
            
        except Exception as e:
            logger.error(f"Error calculating viewing patterns for user {user_id}: {e}")
            return ViewingPatterns(user_id=user_id, analysis_period_days=days)
    
    def get_user_statistics(self, user_id: uuid.UUID) -> UserStats:
        """Get comprehensive user statistics"""
        try:
            # Basic counts
            total_ratings = self.db.query(Rating).filter(Rating.user_id == user_id).count()
            total_reviews = self.db.query(Review).filter(Review.user_id == user_id).count()
            total_activities = self.db.query(UserActivity).filter(UserActivity.user_id == user_id).count()
            
            # Recent activity (last 7 days)
            week_ago = datetime.utcnow() - timedelta(days=7)
            recent_activities = self.db.query(UserActivity).filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= week_ago
                )
            ).count()
            
            # Average rating
            avg_rating_result = self.db.query(func.avg(Rating.rating)).filter(
                Rating.user_id == user_id
            ).scalar()
            avg_rating = float(avg_rating_result) if avg_rating_result else 0.0
            
            # Most rated genre
            most_rated_genre_result = self.db.query(
                Genre.name,
                func.count(Rating.id).label('rating_count')
            ).join(Movie.genres).join(Rating, Movie.id == Rating.movie_id).filter(
                Rating.user_id == user_id
            ).group_by(Genre.name).order_by(desc('rating_count')).first()
            
            most_rated_genre = most_rated_genre_result[0] if most_rated_genre_result else None
            
            # Rating distribution
            rating_dist = self.db.query(
                Rating.rating,
                func.count(Rating.rating)
            ).filter(Rating.user_id == user_id).group_by(Rating.rating).all()
            
            rating_distribution = {str(rating): count for rating, count in rating_dist}
            
            return UserStats(
                user_id=user_id,
                total_ratings=total_ratings,
                total_reviews=total_reviews,
                total_activities=total_activities,
                recent_activity_count=recent_activities,
                average_rating=round(avg_rating, 2),
                most_rated_genre=most_rated_genre,
                rating_distribution=rating_distribution,
                account_age_days=(datetime.utcnow() - self._get_user_created_date(user_id)).days,
                engagement_score=self._calculate_engagement_score(user_id)
            )
            
        except Exception as e:
            logger.error(f"Error calculating user statistics for {user_id}: {e}")
            return UserStats(user_id=user_id)
    
    def get_recommendation_performance(self, user_id: uuid.UUID) -> RecommendationPerformance:
        """Get performance metrics for user's recommendations"""
        try:
            # This would typically involve tracking recommendation clicks, ratings, etc.
            # For now, return basic structure
            return RecommendationPerformance(
                user_id=user_id,
                total_recommendations_received=0,
                recommendations_acted_on=0,
                click_through_rate=0.0,
                average_rating_of_recommended=0.0,
                recommendation_accuracy=0.0,
                favorite_recommendation_type="personal"
            )
            
        except Exception as e:
            logger.error(f"Error calculating recommendation performance for {user_id}: {e}")
            return RecommendationPerformance(user_id=user_id)

    def get_movie_trends(self, genre: Optional[str] = None, days: int = 7) -> MovieTrendAnalysis:
        """Get movie trend analysis"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Base query for activities in time range
            activity_query = self.db.query(UserActivity).filter(
                UserActivity.created_at >= start_date
            )
            
            # Filter by genre if specified
            if genre:
                activity_query = activity_query.join(
                    Movie, UserActivity.movie_id == Movie.id
                ).join(
                    Movie.genres
                ).filter(Genre.name == genre)
            
            # Most viewed movies
            most_viewed = activity_query.filter(
                UserActivity.activity_type == "view"
            ).with_entities(
                UserActivity.movie_id,
                func.count(UserActivity.id).label('view_count')
            ).group_by(UserActivity.movie_id).order_by(desc('view_count')).limit(10).all()
            
            # Most rated movies
            most_rated = activity_query.filter(
                UserActivity.activity_type == "rate"
            ).with_entities(
                UserActivity.movie_id,
                func.count(UserActivity.id).label('rating_count')
            ).group_by(UserActivity.movie_id).order_by(desc('rating_count')).limit(10).all()
            
            # Trending genres (if not filtered by genre)
            trending_genres = []
            if not genre:
                trending_genres_query = self.db.query(
                    Genre.name,
                    func.count(UserActivity.id).label('activity_count')
                ).join(Movie.genres).join(
                    UserActivity, Movie.id == UserActivity.movie_id
                ).filter(
                    UserActivity.created_at >= start_date
                ).group_by(Genre.name).order_by(desc('activity_count')).limit(5).all()
                
                trending_genres = [{"genre": name, "activity_count": count} 
                                 for name, count in trending_genres_query]
            
            return MovieTrendAnalysis(
                analysis_period_days=days,
                genre_filter=genre,
                most_viewed_movies=[{"movie_id": movie_id, "view_count": count} 
                                  for movie_id, count in most_viewed],
                most_rated_movies=[{"movie_id": movie_id, "rating_count": count} 
                                 for movie_id, count in most_rated],
                trending_genres=trending_genres,
                total_activities=activity_query.count(),
                peak_activity_date=self._get_peak_activity_date(start_date, end_date)
            )
            
        except Exception as e:
            logger.error(f"Error calculating movie trends: {e}")
            return MovieTrendAnalysis(analysis_period_days=days, genre_filter=genre)
    
    # Helper methods
    def _calculate_decade_preferences(self, ratings: List[Rating]) -> Dict[str, Any]:
        """Calculate user's decade preferences"""
        decade_ratings = {}
        
        for rating in ratings:
            if rating.movie and rating.movie.release_date:
                decade = (rating.movie.release_date.year // 10) * 10
                decade_key = f"{decade}s"
                
                if decade_key not in decade_ratings:
                    decade_ratings[decade_key] = []
                
                decade_ratings[decade_key].append(rating.rating)
        
        decade_preferences = {}
        for decade, ratings_list in decade_ratings.items():
            if len(ratings_list) >= 3:  # Minimum 3 ratings for significance
                avg_rating = sum(ratings_list) / len(ratings_list)
                decade_preferences[decade] = {
                    "average_rating": round(avg_rating, 2),
                    "count": len(ratings_list)
                }
        
        return decade_preferences
    
    def _calculate_language_preferences(self, ratings: List[Rating]) -> Dict[str, Any]:
        """Calculate user's language preferences"""
        language_ratings = {}
        
        for rating in ratings:
            if rating.movie and rating.movie.original_language:
                lang = rating.movie.original_language
                
                if lang not in language_ratings:
                    language_ratings[lang] = []
                
                language_ratings[lang].append(rating.rating)
        
        language_preferences = {}
        for lang, ratings_list in language_ratings.items():
            if len(ratings_list) >= 2:  # Minimum 2 ratings
                avg_rating = sum(ratings_list) / len(ratings_list)
                language_preferences[lang] = {
                    "average_rating": round(avg_rating, 2),
                    "count": len(ratings_list)
                }
        
        return language_preferences
    
    def _calculate_runtime_preferences(self, ratings: List[Rating]) -> Dict[str, Any]:
        """Calculate user's runtime preferences"""
        runtime_categories = {
            "short": [],      # < 90 minutes
            "medium": [],     # 90-120 minutes
            "long": [],       # 120-150 minutes
            "very_long": []   # > 150 minutes
        }
        
        for rating in ratings:
            if rating.movie and rating.movie.runtime:
                runtime = rating.movie.runtime
                
                if runtime < 90:
                    category = "short"
                elif runtime < 120:
                    category = "medium"
                elif runtime < 150:
                    category = "long"
                else:
                    category = "very_long"
                
                runtime_categories[category].append(rating.rating)
        
        runtime_preferences = {}
        for category, ratings_list in runtime_categories.items():
            if ratings_list:
                avg_rating = sum(ratings_list) / len(ratings_list)
                runtime_preferences[category] = {
                    "average_rating": round(avg_rating, 2),
                    "count": len(ratings_list)
                }
        
        return runtime_preferences
    
    def _calculate_mood_preferences(self, genre_preferences: Dict[str, Any]) -> Dict[str, float]:
        """Calculate mood preferences based on genre preferences"""
        # Map genres to moods
        genre_mood_mapping = {
            "Action": ["energetic", "excited"],
            "Adventure": ["adventurous", "excited"],
            "Comedy": ["happy", "relaxed"],
            "Drama": ["thoughtful", "sad"],
            "Horror": ["scared"],
            "Romance": ["romantic", "happy"],
            "Thriller": ["excited", "scared"],
            "Documentary": ["thoughtful"],
            "Family": ["happy", "relaxed"],
            "Fantasy": ["adventurous", "excited"],
            "Science Fiction": ["thoughtful", "excited"],
            "Mystery": ["thoughtful"],
            "Crime": ["excited", "thoughtful"]
        }
        
        mood_scores = {}
        
        for genre, data in genre_preferences.items():
            if genre in genre_mood_mapping:
                weight = data["preference_score"] * data["count"] / 100.0
                
                for mood in genre_mood_mapping[genre]:
                    if mood not in mood_scores:
                        mood_scores[mood] = 0
                    mood_scores[mood] += weight
        
        # Normalize scores
        if mood_scores:
            max_score = max(mood_scores.values())
            if max_score > 0:
                mood_scores = {mood: score / max_score for mood, score in mood_scores.items()}
        
        return mood_scores
    
    def _calculate_rating_variance(self, ratings: List[Rating]) -> float:
        """Calculate variance in user's ratings"""
        if len(ratings) < 2:
            return 0.0
        
        ratings_values = [r.rating for r in ratings]
        mean_rating = sum(ratings_values) / len(ratings_values)
        variance = sum((r - mean_rating) ** 2 for r in ratings_values) / len(ratings_values)
        
        return round(variance, 3)
    
    def _calculate_diversity_score(self, ratings: List[Rating]) -> float:
        """Calculate how diverse user's movie choices are"""
        if not ratings:
            return 0.0
        
        # Count unique genres
        unique_genres = set()
        for rating in ratings:
            if rating.movie and rating.movie.genres:
                for genre in rating.movie.genres:
                    unique_genres.add(genre.name)
        
        # Count unique decades
        unique_decades = set()
        for rating in ratings:
            if rating.movie and rating.movie.release_date:
                decade = (rating.movie.release_date.year // 10) * 10
                unique_decades.add(decade)
        
        # Simple diversity score based on genre and decade variety
        genre_diversity = min(len(unique_genres) / 10.0, 1.0)  # Max 10 genres
        decade_diversity = min(len(unique_decades) / 8.0, 1.0)  # Max 8 decades
        
        return round((genre_diversity + decade_diversity) / 2.0, 2)
    
    def _calculate_binge_score(self, activities: List[UserActivity]) -> float:
        """Calculate binge watching score based on activity patterns"""
        if len(activities) < 5:
            return 0.0
        
        # Sort activities by date
        activities.sort(key=lambda x: x.created_at)
        
        # Look for clusters of activity
        binge_sessions = 0
        current_session_count = 0
        
        for i in range(1, len(activities)):
            time_diff = (activities[i].created_at - activities[i-1].created_at).total_seconds() / 3600
            
            if time_diff < 4:  # Within 4 hours
                current_session_count += 1
            else:
                if current_session_count >= 3:  # 3+ activities in session = binge
                    binge_sessions += 1
                current_session_count = 0
        
        # Final check
        if current_session_count >= 3:
            binge_sessions += 1
        
        # Normalize to 0-1 scale
        max_possible_sessions = len(activities) / 5
        return min(binge_sessions / max_possible_sessions, 1.0) if max_possible_sessions > 0 else 0.0
    
    def _calculate_engagement_score(self, user_id: uuid.UUID) -> float:
        """Calculate user engagement score"""
        try:
            # Get various engagement metrics
            total_ratings = self.db.query(Rating).filter(Rating.user_id == user_id).count()
            total_reviews = self.db.query(Review).filter(Review.user_id == user_id).count()
            
            # Recent activity (last 30 days)
            month_ago = datetime.utcnow() - timedelta(days=30)
            recent_activity = self.db.query(UserActivity).filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= month_ago
                )
            ).count()
            
            # Simple engagement score calculation
            rating_score = min(total_ratings / 50.0, 1.0)  # Max at 50 ratings
            review_score = min(total_reviews / 10.0, 1.0)  # Max at 10 reviews
            activity_score = min(recent_activity / 30.0, 1.0)  # Max at 30 recent activities
            
            engagement_score = (rating_score * 0.4 + review_score * 0.3 + activity_score * 0.3)
            return round(engagement_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating engagement score: {e}")
            return 0.0
    
    def _get_user_created_date(self, user_id: uuid.UUID) -> datetime:
        """Get user's account creation date"""
        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            return user.created_at if user else datetime.utcnow()
        except Exception:
            return datetime.utcnow()
    
    def _get_day_name(self, day_index: int) -> str:
        """Convert day index to day name"""
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        return days[day_index] if 0 <= day_index < 7 else "Unknown"
    
    def _get_peak_activity_date(self, start_date: datetime, end_date: datetime) -> Optional[str]:
        """Get the date with peak activity in the given range"""
        try:
            peak_date_result = self.db.query(
                func.date(UserActivity.created_at).label('activity_date'),
                func.count(UserActivity.id).label('activity_count')
            ).filter(
                UserActivity.created_at.between(start_date, end_date)
            ).group_by('activity_date').order_by(desc('activity_count')).first()
            
            return peak_date_result.activity_date.isoformat() if peak_date_result else None
            
        except Exception as e:
            logger.error(f"Error getting peak activity date: {e}")
            return None