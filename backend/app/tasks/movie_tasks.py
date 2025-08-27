"""
Movie-related background tasks
"""
from celery import current_task
from sqlalchemy.orm import Session
from sqlalchemy import or_  # missing import
import logging
from datetime import datetime, timedelta  # timedelta was missing
from typing import Optional

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.tmdb.client import TMDBClient
from app.models.movie import Movie, Genre, MovieStats
from app.models.rating import Rating

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
async def sync_trending_movies(self):
    """Sync trending movies from TMDB"""
    try:
        db = SessionLocal()
        tmdb_client = TMDBClient()
        
        logger.info("Starting trending movies sync...")
        
        # Get trending movies for different time periods
        trending_today = await tmdb_client.get_trending_movies("day")
        trending_week = await tmdb_client.get_trending_movies("week")
        
        synced_count = 0
        
        # Combine and process all trending movies
        all_trending = trending_today + trending_week
        unique_movies = {movie.id: movie for movie in all_trending}
        
        for movie_data in unique_movies.values():
            try:
                # Check if movie already exists
                existing_movie = db.query(Movie).filter(Movie.id == movie_data.id).first()
                
                if existing_movie:
                    # Update existing movie
                    existing_movie.popularity = movie_data.popularity
                    existing_movie.vote_average = movie_data.vote_average
                    existing_movie.vote_count = movie_data.vote_count
                    existing_movie.last_updated = datetime.utcnow()
                else:
                    # Get detailed movie information
                    detailed_movie = await tmdb_client.get_movie_details(movie_data.id)
                    if detailed_movie:
                        # Create new movie record
                        new_movie = Movie(
                            id=detailed_movie.id,
                            title=detailed_movie.title,
                            original_title=detailed_movie.original_title,
                            overview=detailed_movie.overview,
                            tagline=detailed_movie.tagline,
                            release_date=detailed_movie.release_date,
                            runtime=detailed_movie.runtime,
                            poster_path=detailed_movie.poster_path,
                            backdrop_path=detailed_movie.backdrop_path,
                            vote_average=detailed_movie.vote_average,
                            vote_count=detailed_movie.vote_count,
                            popularity=detailed_movie.popularity,
                            adult=detailed_movie.adult,
                            original_language=detailed_movie.original_language,
                            budget=detailed_movie.budget,
                            revenue=detailed_movie.revenue,
                            homepage=detailed_movie.homepage,
                            status=detailed_movie.status,
                            trailer_url=detailed_movie.trailer_url,
                            is_active=True
                        )
                        
                        db.add(new_movie)
                        
                        # Add genres
                        for genre_data in detailed_movie.genres:
                            genre = db.query(Genre).filter(Genre.id == genre_data.id).first()
                            if not genre:
                                genre = Genre(id=genre_data.id, name=genre_data.name)
                                db.add(genre)
                            
                            if genre not in new_movie.genres:
                                new_movie.genres.append(genre)
                
                synced_count += 1
                
                # Commit every 10 movies
                if synced_count % 10 == 0:
                    db.commit()
                    current_task.update_state(
                        state='PROGRESS',
                        meta={'current': synced_count, 'total': len(unique_movies)}
                    )
                    
            except Exception as e:
                logger.error(f"Error syncing movie {movie_data.id}: {e}")
                continue
        
        # Final commit
        db.commit()
        
        logger.info(f"Trending movies sync completed. Synced {synced_count} movies")
        
        return {
            'status': 'completed',
            'synced_count': synced_count,
            'total_movies': len(unique_movies)
        }
        
    except Exception as e:
        logger.error(f"Error in trending movies sync: {e}")
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying... Attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        raise
    finally:
        if 'db' in locals():
            db.close()
        if 'tmdb_client' in locals():
            await tmdb_client.close()


@celery_app.task(bind=True, max_retries=3)
async def sync_movie_details(self, movie_id: int):
    """Sync detailed information for a specific movie"""
    try:
        db = SessionLocal()
        tmdb_client = TMDBClient()
        
        logger.info(f"Syncing details for movie ID: {movie_id}")
        
        # Get detailed movie information from TMDB
        detailed_movie = await tmdb_client.get_movie_details(movie_id)
        
        if not detailed_movie:
            logger.warning(f"Movie {movie_id} not found in TMDB")
            return {'status': 'not_found', 'movie_id': movie_id}
        
        # Check if movie exists in database
        existing_movie = db.query(Movie).filter(Movie.id == movie_id).first()
        
        if existing_movie:
            # Update existing movie
            existing_movie.title = detailed_movie.title
            existing_movie.original_title = detailed_movie.original_title
            existing_movie.overview = detailed_movie.overview
            existing_movie.tagline = detailed_movie.tagline
            existing_movie.release_date = detailed_movie.release_date
            existing_movie.runtime = detailed_movie.runtime
            existing_movie.poster_path = detailed_movie.poster_path
            existing_movie.backdrop_path = detailed_movie.backdrop_path
            existing_movie.vote_average = detailed_movie.vote_average
            existing_movie.vote_count = detailed_movie.vote_count
            existing_movie.popularity = detailed_movie.popularity
            existing_movie.budget = detailed_movie.budget
            existing_movie.revenue = detailed_movie.revenue
            existing_movie.homepage = detailed_movie.homepage
            existing_movie.status = detailed_movie.status
            existing_movie.trailer_url = detailed_movie.trailer_url
            existing_movie.last_updated = datetime.utcnow()
            
            movie = existing_movie
        else:
            # Create new movie
            movie = Movie(
                id=detailed_movie.id,
                title=detailed_movie.title,
                original_title=detailed_movie.original_title,
                overview=detailed_movie.overview,
                tagline=detailed_movie.tagline,
                release_date=detailed_movie.release_date,
                runtime=detailed_movie.runtime,
                poster_path=detailed_movie.poster_path,
                backdrop_path=detailed_movie.backdrop_path,
                vote_average=detailed_movie.vote_average,
                vote_count=detailed_movie.vote_count,
                popularity=detailed_movie.popularity,
                adult=detailed_movie.adult,
                original_language=detailed_movie.original_language,
                budget=detailed_movie.budget,
                revenue=detailed_movie.revenue,
                homepage=detailed_movie.homepage,
                status=detailed_movie.status,
                trailer_url=detailed_movie.trailer_url,
                is_active=True
            )
            db.add(movie)
        
        # Update genres
        movie.genres.clear()  # Clear existing genres
        
        for genre_data in detailed_movie.genres:
            genre = db.query(Genre).filter(Genre.id == genre_data.id).first()
            if not genre:
                genre = Genre(id=genre_data.id, name=genre_data.name)
                db.add(genre)
            
            movie.genres.append(genre)
        
        db.commit()
        
        logger.info(f"Successfully synced movie {movie_id}: {movie.title}")
        
        return {
            'status': 'success',
            'movie_id': movie_id,
            'title': movie.title
        }
        
    except Exception as e:
        logger.error(f"Error syncing movie {movie_id}: {e}")
        
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying movie sync... Attempt {self.request.retries + 1}")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        
        return {
            'status': 'error',
            'movie_id': movie_id,
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()
        if 'tmdb_client' in locals():
            await tmdb_client.close()


@celery_app.task
async def update_movie_ratings():
    """Update movie ratings from TMDB"""
    try:
        db = SessionLocal()
        tmdb_client = TMDBClient()
        
        logger.info("Starting movie ratings update...")
        
        # Get movies that haven't been updated recently (older than 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        movies_to_update = db.query(Movie).filter(
            or_(
                Movie.last_updated.is_(None),
                Movie.last_updated < cutoff_time
            ),
            Movie.is_active == True
        ).limit(100).all()  # Update 100 movies at a time
        
        updated_count = 0
        
        for movie in movies_to_update:
            try:
                # Get basic movie info from TMDB
                basic_info = await tmdb_client._make_request(f"/movie/{movie.id}")
                
                if basic_info:
                    movie.vote_average = basic_info.get('vote_average')
                    movie.vote_count = basic_info.get('vote_count')
                    movie.popularity = basic_info.get('popularity')
                    movie.last_updated = datetime.utcnow()
                    
                    updated_count += 1
                
            except Exception as e:
                logger.error(f"Error updating ratings for movie {movie.id}: {e}")
                continue
        
        db.commit()
        
        logger.info(f"Movie ratings update completed. Updated {updated_count} movies")
        
        return {
            'status': 'completed',
            'updated_count': updated_count,
            'total_checked': len(movies_to_update)
        }
        
    except Exception as e:
        logger.error(f"Error in movie ratings update: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()
        if 'tmdb_client' in locals():
            await tmdb_client.close()


@celery_app.task
def update_movie_stats(movie_id: int, activity_type: str):
    """Update movie statistics based on user activity"""
    try:
        db = SessionLocal()
        
        # Get or create movie stats
        movie_stats = db.query(MovieStats).filter(
            MovieStats.movie_id == movie_id
        ).first()
        
        if not movie_stats:
            movie_stats = MovieStats(movie_id=movie_id)
            db.add(movie_stats)
        
        # Update stats based on activity type
        if activity_type == "view":
            movie_stats.view_count += 1
        elif activity_type == "rate":
            movie_stats.rating_count += 1
            # Recalculate average rating
            ratings = db.query(Rating).filter(Rating.movie_id == movie_id).all()
            if ratings:
                movie_stats.average_rating = sum(r.rating for r in ratings) / len(ratings)
        elif activity_type == "review":
            movie_stats.review_count += 1
        elif activity_type == "watchlist":
            movie_stats.watchlist_count += 1
        
        movie_stats.last_calculated = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Updated stats for movie {movie_id}: {activity_type}")
        
        return {
            'status': 'success',
            'movie_id': movie_id,
            'activity_type': activity_type
        }
        
    except Exception as e:
        logger.error(f"Error updating movie stats: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()


@celery_app.task
async def sync_movie_genres():
    """Sync movie genres from TMDB"""
    try:
        db = SessionLocal()
        tmdb_client = TMDBClient()
        
        logger.info("Syncing movie genres...")
        
        # Get genres from TMDB
        genres_data = await tmdb_client._make_request("/genre/movie/list")
        
        if not genres_data or 'genres' not in genres_data:
            logger.error("No genre data received from TMDB")
            return {'status': 'error', 'error': 'No genre data'}
        
        synced_count = 0
        
        for genre_data in genres_data['genres']:
            genre = db.query(Genre).filter(Genre.id == genre_data['id']).first()
            
            if not genre:
                genre = Genre(
                    id=genre_data['id'],
                    name=genre_data['name']
                )
                db.add(genre)
                synced_count += 1
            else:
                # Update name if changed
                if genre.name != genre_data['name']:
                    genre.name = genre_data['name']
                    synced_count += 1
        
        db.commit()
        
        logger.info(f"Genre sync completed. Synced {synced_count} genres")
        
        return {
            'status': 'completed',
            'synced_count': synced_count
        }
        
    except Exception as e:
        logger.error(f"Error syncing genres: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()
        if 'tmdb_client' in locals():
            await tmdb_client.close()


@celery_app.task
def cleanup_inactive_movies():
    """Cleanup movies that are no longer relevant"""
    try:
        db = SessionLocal()
        
        logger.info("Starting movie cleanup...")
        
        # Mark movies as inactive if they have very low engagement
        # and haven't been updated in a long time
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        inactive_movies = db.query(Movie).filter(
            Movie.vote_count < 5,
            Movie.popularity < 1.0,
            Movie.last_updated < cutoff_date,
            Movie.is_active == True
        ).all()
        
        cleaned_count = 0
        
        for movie in inactive_movies:
            # Check if movie has any user ratings
            has_ratings = db.query(Rating).filter(Rating.movie_id == movie.id).first()
            
            if not has_ratings:
                movie.is_active = False
                cleaned_count += 1
        
        db.commit()
        
        logger.info(f"Movie cleanup completed. Deactivated {cleaned_count} movies")
        
        return {
            'status': 'completed',
            'cleaned_count': cleaned_count
        }
        
    except Exception as e:
        logger.error(f"Error in movie cleanup: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
        
    finally:
        if 'db' in locals():
            db.close()
