"""
Analytics-related background tasks
"""
from celery import current_task
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import logging
from datetime import datetime, timedelta
import uuid
import json
from typing import Optional, Dict, Any

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.cache.redis_client import RedisCache
from app.models.user import User, UserActivity
from app.models.movie import Movie, MovieStats
from app.models.rating import Rating, Review
from app.models.social import Friendship

logger = logging.getLogger(__name__)


@celery_app.task
def track_user_activity(user_id_str: str, activity_type: str, movie_id: Optional[int] = None, 
                       search_query: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None,
                       session_id: Optional[str] = None, user_agent: Optional[str] = None,
                       ip_address: Optional[str] = None):
    """Track user activity for analytics and recommendations"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()

        logger.info(f"Tracking activity: {activity_type} for user {user_id}")

        # Create user activity record
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            movie_id=movie_id,
            search_query=search_query,
            activity_metadata=json.dumps(metadata) if metadata else None,
            session_id=session_id,
            user_agent=user_agent,
            ip_address=ip_address
        )

        db.add(activity)

        # Update user's last activity
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.last_login = datetime.utcnow()

        # Update movie stats if movie-related activity
        if movie_id and activity_type in ['view', 'rate', 'review', 'watchlist_add']:
            movie_stats = db.query(MovieStats).filter(MovieStats.movie_id == movie_id).first()
            if not movie_stats:
                movie_stats = MovieStats(movie_id=movie_id)
                db.add(movie_stats)

            if activity_type == 'view':
                movie_stats.view_count += 1
            elif activity_type == 'rate':
                movie_stats.rating_count += 1
            elif activity_type == 'review':
                movie_stats.review_count += 1
            elif activity_type == 'watchlist_add':
                movie_stats.watchlist_count += 1

            movie_stats.last_calculated = datetime.utcnow()

        db.commit()

        logger.info(f"Successfully tracked {activity_type} activity for user {user_id}")

        return {
            'status': 'success',
            'user_id': str(user_id),
            'activity_type': activity_type,
            'movie_id': movie_id
        }

    except Exception as e:
        logger.error(f"Error tracking user activity: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
def calculate_user_engagement_metrics(user_id_str: str):
    """Calculate comprehensive user engagement metrics"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()
        cache = RedisCache()

        logger.info(f"Calculating engagement metrics for user {user_id}")

        # Get user activities from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        activities = db.query(UserActivity).filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= thirty_days_ago
        ).all()

        # Calculate various metrics
        metrics = {
            'total_activities': len(activities),
            'activity_breakdown': {},
            'movies_viewed': 0,
            'searches_performed': 0,
            'ratings_given': 0,
            'reviews_written': 0,
            'average_session_duration': 0,
            'most_active_day': None,
            'engagement_score': 0
        }

        # Activity breakdown
        activity_counts = {}
        movie_views = set()
        search_count = 0
        
        for activity in activities:
            activity_type = activity.activity_type
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
            
            if activity_type == 'view' and activity.movie_id:
                movie_views.add(activity.movie_id)
            elif activity_type == 'search':
                search_count += 1

        metrics['activity_breakdown'] = activity_counts
        metrics['movies_viewed'] = len(movie_views)
        metrics['searches_performed'] = search_count

        # Get ratings and reviews from database
        ratings_count = db.query(Rating).filter(
            Rating.user_id == user_id,
            Rating.created_at >= thirty_days_ago
        ).count()
        
        reviews_count = db.query(Review).filter(
            Review.user_id == user_id,
            Review.created_at >= thirty_days_ago
        ).count()

        metrics['ratings_given'] = ratings_count
        metrics['reviews_written'] = reviews_count

        # Calculate engagement score (0-100)
        engagement_score = min(100, (
            len(activities) * 2 +  # General activity
            len(movie_views) * 5 +  # Movie variety
            ratings_count * 10 +   # Ratings (high value)
            reviews_count * 15 +   # Reviews (highest value)
            search_count * 3       # Search activity
        ) / 10)

        metrics['engagement_score'] = round(engagement_score, 2)

        # Cache the metrics
        cache_key = f"user_engagement_{user_id}"
        cache.set_sync(cache_key, metrics, ttl=3600)  # Cache for 1 hour

        logger.info(f"Calculated engagement metrics for user {user_id}: score={engagement_score}")

        return {
            'status': 'success',
            'user_id': str(user_id),
            'metrics': metrics
        }

    except Exception as e:
        logger.error(f"Error calculating engagement metrics: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
def generate_user_insights(user_id_str: str):
    """Generate personalized insights for a user"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()

        logger.info(f"Generating insights for user {user_id}")

        # Get user's ratings and preferences
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        
        if len(user_ratings) < 5:
            return {
                'status': 'insufficient_data',
                'message': 'User needs at least 5 ratings for insights'
            }

        insights = {
            'favorite_genres': [],
            'rating_patterns': {},
            'viewing_trends': {},
            'recommendations': [],
            'taste_evolution': {}
        }

        # Analyze favorite genres
        genre_ratings = {}
        for rating in user_ratings:
            if rating.movie and rating.movie.genres:
                for genre in rating.movie.genres:
                    if genre.name not in genre_ratings:
                        genre_ratings[genre.name] = []
                    genre_ratings[genre.name].append(rating.rating)

        # Calculate average rating per genre
        genre_averages = {}
        for genre, ratings in genre_ratings.items():
            if len(ratings) >= 2:  # At least 2 ratings
                avg_rating = sum(ratings) / len(ratings)
                genre_averages[genre] = {
                    'average_rating': round(avg_rating, 2),
                    'count': len(ratings)
                }

        # Sort by average rating
        insights['favorite_genres'] = sorted(
            genre_averages.items(),
            key=lambda x: x[1]['average_rating'],
            reverse=True
        )[:5]

        # Rating patterns
        total_ratings = len(user_ratings)
        rating_distribution = {}
        for rating in user_ratings:
            r = rating.rating
            rating_distribution[str(r)] = rating_distribution.get(str(r), 0) + 1

        insights['rating_patterns'] = {
            'total_ratings': total_ratings,
            'average_rating': round(sum(r.rating for r in user_ratings) / total_ratings, 2),
            'distribution': rating_distribution,
            'most_common_rating': max(rating_distribution, key=rating_distribution.get)
        }

        # Cache insights
        cache = RedisCache()
        cache_key = f"user_insights_{user_id}"
        cache.set_sync(cache_key, insights, ttl=7200)  # Cache for 2 hours

        logger.info(f"Generated insights for user {user_id}")

        return {
            'status': 'success',
            'user_id': str(user_id),
            'insights': insights
        }

    except Exception as e:
        logger.error(f"Error generating user insights: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
def analyze_platform_metrics():
    """Analyze overall platform metrics"""
    try:
        db = SessionLocal()

        logger.info("Analyzing platform metrics...")

        # Calculate various platform metrics
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_week = now - timedelta(days=7)
        last_month = now - timedelta(days=30)

        metrics = {
            'users': {
                'total': db.query(User).count(),
                'active_24h': db.query(UserActivity).filter(
                    UserActivity.created_at >= last_24h
                ).distinct(UserActivity.user_id).count(),
                'active_week': db.query(UserActivity).filter(
                    UserActivity.created_at >= last_week
                ).distinct(UserActivity.user_id).count(),
                'new_this_month': db.query(User).filter(
                    User.created_at >= last_month
                ).count()
            },
            'content': {
                'total_movies': db.query(Movie).filter(Movie.is_active == True).count(),
                'total_ratings': db.query(Rating).count(),
                'total_reviews': db.query(Review).count(),
                'average_rating': db.query(func.avg(Rating.rating)).scalar() or 0
            },
            'activity': {
                'activities_24h': db.query(UserActivity).filter(
                    UserActivity.created_at >= last_24h
                ).count(),
                'activities_week': db.query(UserActivity).filter(
                    UserActivity.created_at >= last_week
                ).count()
            }
        }

        # Round average rating
        metrics['content']['average_rating'] = round(metrics['content']['average_rating'], 2)

        # Cache platform metrics
        cache = RedisCache()
        cache.set_sync('platform_metrics', metrics, ttl=3600)  # Cache for 1 hour

        logger.info("Platform metrics analysis completed")

        return {
            'status': 'success',
            'metrics': metrics
        }

    except Exception as e:
        logger.error(f"Error analyzing platform metrics: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
def cleanup_old_activities():
    """Clean up old user activities to maintain database performance"""
    try:
        db = SessionLocal()

        logger.info("Starting cleanup of old activities...")

        # Keep activities for last 6 months
        cutoff_date = datetime.utcnow() - timedelta(days=180)

        # Count activities to be deleted
        old_activities_count = db.query(UserActivity).filter(
            UserActivity.created_at < cutoff_date
        ).count()

        # Delete old activities
        deleted = db.query(UserActivity).filter(
            UserActivity.created_at < cutoff_date
        ).delete()

        db.commit()

        logger.info(f"Cleaned up {deleted} old activities")

        return {
            'status': 'success',
            'deleted_count': deleted,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up old activities: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
def update_recommendation_metrics(user_id_str: str, recommendation_id: str, action: str):
    """Track recommendation interactions for improving ML models"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()

        logger.info(f"Updating recommendation metrics: {action} for user {user_id}")

        # Track the recommendation interaction
        track_user_activity(
            user_id_str=user_id_str,
            activity_type='recommendation_interaction',
            metadata={
                'recommendation_id': recommendation_id,
                'action': action,
                'timestamp': datetime.utcnow().isoformat()
            }
        )

        # Update recommendation performance metrics
        cache = RedisCache()
        metrics_key = f"recommendation_metrics_{recommendation_id}"
        
        current_metrics = cache.get_sync(metrics_key) or {
            'views': 0,
            'clicks': 0,
            'ratings': 0,
            'click_through_rate': 0.0
        }

        if action == 'view':
            current_metrics['views'] += 1
        elif action == 'click':
            current_metrics['clicks'] += 1
        elif action == 'rate':
            current_metrics['ratings'] += 1

        # Calculate click-through rate
        if current_metrics['views'] > 0:
            current_metrics['click_through_rate'] = round(
                current_metrics['clicks'] / current_metrics['views'], 4
            )

        # Cache updated metrics
        cache.set_sync(metrics_key, current_metrics, ttl=86400)  # 24 hours

        logger.info(f"Updated recommendation metrics: {current_metrics}")

        return {
            'status': 'success',
            'recommendation_id': recommendation_id,
            'action': action,
            'metrics': current_metrics
        }

    except Exception as e:
        logger.error(f"Error updating recommendation metrics: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

    finally:
        if 'db' in locals():
            db.close()