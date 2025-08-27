"""
Recommendation-related background tasks
"""
from celery import current_task
from sqlalchemy.orm import Session
import logging
from datetime import datetime, timedelta
import uuid
import json

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.ml.content_based import ContentBasedRecommender
from app.services.ml.collaborative import CollaborativeRecommender
from app.services.ml.hybrid_recommender import HybridRecommender
from app.services.ml.mood_analyzer import MoodAnalyzer
from app.services.cache.redis_client import RedisCache
from app.models.user import User
from app.models.rating import Rating, Review

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def generate_user_recommendations(self, user_id_str: str):
    """Generate and cache recommendations for a user"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()
        cache = RedisCache()

        logger.info(f"Generating recommendations for user {user_id}")
        
        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return {'status': 'error', 'error': 'User not found'}
        
        # Generate recommendations using hybrid approach
        hybrid_recommender = HybridRecommender(db)
        
        # Generate different types of recommendations (sync methods)
        recommendations = {}
        
        # Personal recommendations
        personal_recs = hybrid_recommender.get_personal_recommendations_sync(user_id, limit=20)
        recommendations['personal'] = [rec.dict() for rec in personal_recs]
        
        # Trending personalized
        trending_recs = hybrid_recommender.get_personalized_trending_sync(user_id, limit=15)
        recommendations['trending'] = [rec.dict() for rec in trending_recs]
        
        # Cache recommendations for different limits
        for limit in [5, 10, 15, 20]:
            cache_key = f"recommendations_personal_{user_id}_{limit}"
            recs_subset = recommendations['personal'][:limit]
            cache.set_sync(cache_key, recs_subset, ttl=1800)  # 30 minutes
        
        # Cache trending recommendations
        trending_cache_key = f"recommendations_trending_{user_id}_15"
        cache.set_sync(trending_cache_key, recommendations['trending'], ttl=7200)  # 2 hours
        
        logger.info(f"Generated {len(personal_recs)} personal and {len(trending_recs)} trending recommendations for user {user_id}")
        
        return {
            'status': 'success',
            'user_id': str(user_id),
            'personal_count': len(personal_recs),
            'trending_count': len(trending_recs)
        }
        
    except Exception as e:
        logger.error(f"Error generating recommendations for user {user_id_str}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()

@celery_app.task(bind=True, max_retries=2)
def retrain_models(self):
    """Retrain all recommendation models"""
    try:
        db = SessionLocal()

        logger.info("Starting model retraining...")
        
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 3, 'stage': 'content_based'}
        )
        
        # Retrain content-based model
        content_recommender = ContentBasedRecommender(db)
        content_success = content_recommender.train_model_sync()
        
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 3, 'stage': 'collaborative'}
        )
        
        # Retrain collaborative model
        collaborative_recommender = CollaborativeRecommender(db)
        collaborative_success = collaborative_recommender.train_model_sync()
        
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 3, 'stage': 'mood_analysis'}
        )
        
        # Train mood analysis model
        mood_analyzer = MoodAnalyzer(db)
        mood_success = mood_analyzer.train_model_sync()
        
        current_task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 3, 'stage': 'completed'}
        )
        
        success_count = sum([content_success, collaborative_success, mood_success])
        
        logger.info(f"Model retraining completed. {success_count}/3 models trained successfully")
        
        # Clear recommendation caches to force regeneration
        cache = RedisCache()
        cache.delete_pattern_sync("recommendations_*")
        
        return {
            'status': 'completed',
            'models_trained': success_count,
            'content_based': content_success,
            'collaborative': collaborative_success,
            'mood_analysis': mood_success
        }
        
    except Exception as e:
        logger.error(f"Error in model retraining: {e}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying model training... Attempt {self.request.retries + 1}")
            raise self.retry(countdown=300)  # Retry after 5 minutes
        
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()

@celery_app.task
def update_user_taste_profile(user_id_str: str):
    """Update user's taste profile based on latest ratings"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()

        logger.info(f"Updating taste profile for user {user_id}")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {'status': 'error', 'error': 'User not found'}
        
        # Get user's ratings
        user_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
        
        if len(user_ratings) < 3:
            logger.info(f"User {user_id} has insufficient ratings for taste profile")
            return {'status': 'insufficient_data'}
        
        # Calculate taste profile
        taste_profile = _calculate_taste_profile(user_ratings, db)
        
        # Update user's taste profile
        user.taste_profile = json.dumps(taste_profile)
        user.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Clear user's cached recommendations
        cache = RedisCache()
        cache.delete_pattern_sync(f"recommendations_*_{user_id}_*")
        cache.delete_pattern_sync(f"taste_profile_{user_id}")
        
        logger.info(f"Taste profile updated for user {user_id}")
        
        return {
            'status': 'success',
            'user_id': str(user_id),
            'ratings_count': len(user_ratings)
        }
        
    except Exception as e:
        logger.error(f"Error updating taste profile for user {user_id_str}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()

@celery_app.task
def analyze_review_sentiment(review_id_str: str):
    """Analyze sentiment and extract emotions from a review"""
    try:
        review_id = uuid.UUID(review_id_str)
        db = SessionLocal()

        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return {'status': 'error', 'error': 'Review not found'}
        
        if not review.content:
            return {'status': 'error', 'error': 'Review has no content'}
        
        # Analyze sentiment using TextBlob
        from textblob import TextBlob
        
        blob = TextBlob(review.content)
        sentiment_score = blob.sentiment.polarity  # -1 to 1
        
        # Extract emotion tags
        emotion_tags = _extract_emotion_tags(review.content)
        
        # Calculate spoiler probability (simple keyword-based approach)
        spoiler_probability = _calculate_spoiler_probability(review.content)
        
        # Update review
        review.sentiment_score = sentiment_score
        review.emotion_tags = ",".join(emotion_tags) if emotion_tags else None
        review.spoiler_probability = spoiler_probability
        
        db.commit()
        
        logger.info(f"Analyzed sentiment for review {review_id}: sentiment={sentiment_score:.2f}")
        
        return {
            'status': 'success',
            'review_id': str(review_id),
            'sentiment_score': sentiment_score,
            'emotion_tags': emotion_tags,
            'spoiler_probability': spoiler_probability
        }
        
    except Exception as e:
        logger.error(f"Error analyzing review sentiment: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()

@celery_app.task
def generate_mood_recommendations(user_id_str: str, mood: str):
    """Generate mood-based recommendations for a user"""
    try:
        user_id = uuid.UUID(user_id_str)
        db = SessionLocal()
        cache = RedisCache()

        mood_analyzer = MoodAnalyzer(db)
        
        # Generate mood-based recommendations
        recommendations = mood_analyzer.get_mood_recommendations_sync(
            user_id, mood.lower(), limit=15
        )
        
        # Cache results
        cache_key = f"recommendations_mood_{mood}_{user_id}_15"
        cache.set_sync(cache_key, [rec.dict() for rec in recommendations], ttl=3600)
        
        logger.info(f"Generated {len(recommendations)} {mood} recommendations for user {user_id}")
        
        return {
            'status': 'success',
            'user_id': str(user_id),
            'mood': mood,
            'recommendations_count': len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error generating mood recommendations: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()

# Helper functions
def _calculate_taste_profile(user_ratings, db):
    """Calculate user's taste profile from ratings"""
    from collections import defaultdict

    genre_ratings = defaultdict(list)
    decade_ratings = defaultdict(list)
    language_ratings = defaultdict(list)

    for rating in user_ratings:
        movie = rating.movie
        if not movie:
            continue
        
        # Genre preferences
        for genre in movie.genres:
            genre_ratings[genre.name].append(rating.rating)
        
        # Decade preferences
        if movie.release_date:
            decade = (movie.release_date.year // 10) * 10
            decade_ratings[f"{decade}s"].append(rating.rating)
        
        # Language preferences
        if movie.original_language:
            language_ratings[movie.original_language].append(rating.rating)

    # Calculate average ratings
    taste_profile = {
        'genres': {genre: sum(ratings)/len(ratings) 
                  for genre, ratings in genre_ratings.items() 
                  if len(ratings) >= 2},
        'decades': {decade: sum(ratings)/len(ratings) 
                   for decade, ratings in decade_ratings.items() 
                   if len(ratings) >= 2},
        'languages': {lang: sum(ratings)/len(ratings) 
                     for lang, ratings in language_ratings.items() 
                     if len(ratings) >= 2},
        'total_ratings': len(user_ratings),
        'average_rating': sum(r.rating for r in user_ratings) / len(user_ratings),
        'last_updated': datetime.utcnow().isoformat()
    }

    return taste_profile

def _extract_emotion_tags(text: str):
    """Extract emotion tags from review text"""
    text_lower = text.lower()

    emotion_keywords = {
        "happy": ["happy", "joy", "delighted", "amazing", "wonderful", "fantastic"],
        "sad": ["sad", "depressing", "tragic", "heartbreaking", "emotional"],
        "excited": ["exciting", "thrilling", "amazing", "incredible", "awesome"],
        "angry": ["angry", "frustrated", "terrible", "awful", "hate"],
        "scared": ["scary", "frightening", "terrifying", "creepy", "horror"],
        "surprised": ["surprising", "unexpected", "twist", "shocking"],
        "confused": ["confusing", "unclear", "complicated", "strange"],
        "bored": ["boring", "slow", "tedious", "dull"]
    }

    detected_emotions = []
    for emotion, keywords in emotion_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            detected_emotions.append(emotion)

    return detected_emotions

def _calculate_spoiler_probability(text: str):
    """Calculate probability that review contains spoilers"""
    text_lower = text.lower()

    spoiler_indicators = [
        "spoiler", "ending", "dies", "killed", "plot twist", "reveals", "turns out",
        "in the end", "finally", "conclusion", "surprise", "twist", "secret",
        "don't read", "warning", "give away"
    ]

    spoiler_count = sum(1 for indicator in spoiler_indicators if indicator in text_lower)

    # Simple probability calculation
    probability = min(spoiler_count * 0.2, 1.0)

    return probability