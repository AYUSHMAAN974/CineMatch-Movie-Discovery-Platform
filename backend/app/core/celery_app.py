"""
Celery configuration for background tasks
"""
from celery import Celery
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "cinematch",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.movie_tasks",
        "app.tasks.recommendation_tasks",
        "app.tasks.analytics_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_routes={
        "app.tasks.movie_tasks.*": {"queue": "movies"},
        "app.tasks.recommendation_tasks.*": {"queue": "recommendations"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics"},
    },
    task_annotations={
        "app.tasks.recommendation_tasks.generate_user_recommendations": {
            "rate_limit": "10/s"
        },
        "app.tasks.movie_tasks.sync_tmdb_movies": {
            "rate_limit": "5/s"
        }
    }
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "sync-trending-movies": {
        "task": "app.tasks.movie_tasks.sync_trending_movies",
        "schedule": 3600.0,  # Every hour
    },
    "update-movie-ratings": {
        "task": "app.tasks.movie_tasks.update_movie_ratings",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "retrain-recommendation-models": {
        "task": "app.tasks.recommendation_tasks.retrain_models",
        "schedule": 86400.0,  # Daily
    },
    "cleanup-old-cache": {
        "task": "app.tasks.analytics_tasks.cleanup_old_cache",
        "schedule": 7200.0,  # Every 2 hours
    },
}

# Task result expires after 1 hour
celery_app.conf.result_expires = 3600

logger.info("Celery app configured successfully")