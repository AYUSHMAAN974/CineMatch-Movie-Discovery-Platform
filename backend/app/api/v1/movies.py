"""
Movie-related endpoints
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.models.user import User
from app.schemas.movie import (
    Movie, MovieList, MovieDetailed, MovieSearch, MovieFilters,
    TrendingMoviesResponse, Genre
)
from app.services.tmdb.client import TMDBClient
from app.services.cache.redis_client import RedisCache
from app.utils.dependencies import get_current_active_user, get_optional_user
from app.tasks.movie_tasks import sync_movie_details, update_movie_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/trending", response_model=TrendingMoviesResponse)
async def get_trending_movies(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
) -> Any:
    """
    Get trending movies across different categories
    """
    try:
        cache = RedisCache()
        tmdb_client = TMDBClient()
        
        # Try to get from cache first
        cache_key = "trending_movies_all"
        cached_data = await cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Fetch from TMDB
        trending_today = await tmdb_client.get_trending_movies("day")
        trending_week = await tmdb_client.get_trending_movies("week")
        popular = await tmdb_client.get_popular_movies()
        now_playing = await tmdb_client.get_now_playing()
        upcoming = await tmdb_client.get_upcoming()
        top_rated = await tmdb_client.get_top_rated()
        
        response_data = TrendingMoviesResponse(
            trending_today=trending_today[:10],
            trending_week=trending_week[:10],
            popular=popular[:10],
            now_playing=now_playing[:10],
            upcoming=upcoming[:10],
            top_rated=top_rated[:10]
        )
        
        # Cache for 1 hour
        await cache.set(cache_key, response_data.dict(), ttl=3600)
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error fetching trending movies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch trending movies"
        )


@router.get("/search", response_model=MovieList)
async def search_movies(
    query: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    include_adult: bool = Query(False, description="Include adult content"),
    year: Optional[int] = Query(None, ge=1900, le=2030, description="Release year filter"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
) -> Any:
    """
    Search movies using TMDB API
    """
    try:
        tmdb_client = TMDBClient()
        
        # Search movies
        results = await tmdb_client.search_movies(
            query=query,
            page=page,
            include_adult=include_adult,
            year=year
        )
        
        # Log search activity if user is authenticated
        if current_user:
            # Track search activity asynchronously
            from app.tasks.analytics_tasks import track_user_activity
            track_user_activity.delay(
                user_id=str(current_user.id),
                activity_type="search",
                search_query=query
            )
        
        return results
        
    except Exception as e:
        logger.error(f"Movie search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Movie search failed"
        )


@router.get("/discover", response_model=MovieList)
async def discover_movies(
    filters: MovieFilters = Depends(),
    page: int = Query(1, ge=1, le=1000, description="Page number"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
) -> Any:
    """
    Discover movies with advanced filtering
    """
    try:
        tmdb_client = TMDBClient()
        
        # Discover movies with filters
        results = await tmdb_client.discover_movies(
            filters=filters,
            page=page
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Movie discovery error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Movie discovery failed"
        )


@router.get("/genres", response_model=List[Genre])
async def get_movie_genres(
    db: Session = Depends(get_db)
) -> Any:
    """
    Get list of movie genres
    """
    try:
        cache = RedisCache()
        cache_key = "movie_genres"
        
        # Try cache first
        cached_genres = await cache.get(cache_key)
        if cached_genres:
            return cached_genres
        
        # Fetch from TMDB
        tmdb_client = TMDBClient()
        genres = await tmdb_client.get_movie_genres()
        
        # Cache for 24 hours
        await cache.set(cache_key, genres, ttl=86400)
        
        return genres
        
    except Exception as e:
        logger.error(f"Error fetching genres: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch movie genres"
        )


@router.get("/{movie_id}", response_model=MovieDetailed)
async def get_movie_details(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
) -> Any:
    """
    Get detailed movie information
    """
    try:
        tmdb_client = TMDBClient()
        cache = RedisCache()
        
        # Check cache first
        cache_key = f"movie_details_{movie_id}"
        cached_movie = await cache.get(cache_key)
        
        if not cached_movie:
            # Fetch from TMDB
            movie = await tmdb_client.get_movie_details(movie_id)
            
            if not movie:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Movie not found"
                )
            
            # Cache for 6 hours
            await cache.set(cache_key, movie.dict(), ttl=21600)
            cached_movie = movie.dict()
        
        # Add user-specific data if authenticated
        if current_user:
            from app.services.rating_service import RatingService
            rating_service = RatingService(db)
            
            # Get user's rating and watchlist status
            user_rating = rating_service.get_user_movie_rating(current_user.id, movie_id)
            is_in_watchlist = rating_service.is_in_watchlist(current_user.id, movie_id)
            
            cached_movie["user_rating"] = user_rating.rating if user_rating else None
            cached_movie["is_in_watchlist"] = is_in_watchlist
            
            # Track view activity
            from app.tasks.analytics_tasks import track_user_activity
            track_user_activity.delay(
                user_id=str(current_user.id),
                activity_type="view",
                movie_id=movie_id
            )
            
            # Update movie stats
            update_movie_stats.delay(movie_id, "view")
        
        return MovieDetailed(**cached_movie)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching movie details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch movie details"
        )


@router.get("/{movie_id}/similar", response_model=List[Movie])
async def get_similar_movies(
    movie_id: int,
    limit: int = Query(10, ge=1, le=20, description="Number of similar movies"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
) -> Any:
    """
    Get movies similar to the given movie
    """
    try:
        tmdb_client = TMDBClient()
        cache = RedisCache()
        
        cache_key = f"similar_movies_{movie_id}_{limit}"
        cached_similar = await cache.get(cache_key)
        
        if cached_similar:
            return cached_similar
        
        # Get similar movies from TMDB
        similar_movies = await tmdb_client.get_similar_movies(movie_id, limit)
        
        # Cache for 4 hours
        await cache.set(cache_key, [movie.dict() for movie in similar_movies], ttl=14400)
        
        return similar_movies
        
    except Exception as e:
        logger.error(f"Error fetching similar movies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch similar movies"
        )


@router.get("/{movie_id}/credits")
async def get_movie_credits(
    movie_id: int,
    db: Session = Depends(get_db)
) -> Any:
    """
    Get movie cast and crew information
    """
    try:
        tmdb_client = TMDBClient()
        cache = RedisCache()
        
        cache_key = f"movie_credits_{movie_id}"
        cached_credits = await cache.get(cache_key)
        
        if cached_credits:
            return cached_credits
        
        # Get credits from TMDB
        credits = await tmdb_client.get_movie_credits(movie_id)
        
        # Cache for 24 hours
        await cache.set(cache_key, credits, ttl=86400)
        
        return credits
        
    except Exception as e:
        logger.error(f"Error fetching movie credits: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch movie credits"
        )


@router.post("/{movie_id}/sync")
async def sync_movie_data(
    movie_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Manually trigger sync of movie data from TMDB
    (Admin or premium users only)
    """
    if not current_user.is_premium and not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges"
        )
    
    try:
        # Trigger async task to sync movie data
        task = sync_movie_details.delay(movie_id)
        
        return {
            "message": "Movie sync initiated",
            "task_id": task.id,
            "movie_id": movie_id
        }
        
    except Exception as e:
        logger.error(f"Error initiating movie sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate movie sync"
        )