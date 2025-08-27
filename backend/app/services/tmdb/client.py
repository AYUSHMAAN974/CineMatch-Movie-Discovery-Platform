"""
TMDB API client for fetching movie data
"""
import httpx
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import asyncio

from app.core.config import settings
from app.services.tmdb.models import (
    TMDBMovie, TMDBMovieDetails, TMDBGenre, TMDBCredits,
    TMDBSearchResponse, TMDBDiscoverResponse, TMDBVideosResponse
)
from app.schemas.movie import Movie, MovieList, MovieDetailed, Genre, MovieFilters

logger = logging.getLogger(__name__)


class TMDBClient:
    """Client for interacting with TMDB API"""
    
    def __init__(self):
        self.base_url = settings.TMDB_BASE_URL
        self.api_key = settings.TMDB_API_KEY
        self.image_base_url = settings.TMDB_IMAGE_BASE_URL
        self.session = None
    
    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session"""
        if self.session is None:
            self.session = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )
        return self.session
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to TMDB API"""
        try:
            session = await self._get_session()
            
            # Add API key to params
            if params is None:
                params = {}
            params['api_key'] = self.api_key
            
            url = f"{self.base_url}{endpoint}"
            
            response = await session.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"TMDB API HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"TMDB API request error: {e}")
            raise
        except Exception as e:
            logger.error(f"TMDB API unexpected error: {e}")
            raise
    
    def _convert_tmdb_movie_to_movie(self, tmdb_movie: TMDBMovie) -> Movie:
        """Convert TMDB movie model to internal Movie model"""
        return Movie(
            id=tmdb_movie.id,
            title=tmdb_movie.title,
            original_title=tmdb_movie.original_title,
            overview=tmdb_movie.overview,
            release_date=datetime.strptime(tmdb_movie.release_date, "%Y-%m-%d").date() 
                         if tmdb_movie.release_date else None,
            poster_path=tmdb_movie.poster_path,
            backdrop_path=tmdb_movie.backdrop_path,
            adult=tmdb_movie.adult,
            original_language=tmdb_movie.original_language,
            popularity=tmdb_movie.popularity,
            vote_average=tmdb_movie.vote_average,
            vote_count=tmdb_movie.vote_count,
            poster_url=f"{self.image_base_url}/w500{tmdb_movie.poster_path}" 
                      if tmdb_movie.poster_path else None,
            backdrop_url=f"{self.image_base_url}/w1280{tmdb_movie.backdrop_path}" 
                        if tmdb_movie.backdrop_path else None,
            year=datetime.strptime(tmdb_movie.release_date, "%Y-%m-%d").year 
                 if tmdb_movie.release_date else None,
            created_at=datetime.utcnow()
        )
    
    async def get_movie_details(self, movie_id: int) -> Optional[MovieDetailed]:
        """Get detailed information about a movie"""
        try:
            # Get movie details
            movie_data = await self._make_request(f"/movie/{movie_id}")
            tmdb_movie = TMDBMovieDetails(**movie_data)
            
            # Get credits
            credits_data = await self._make_request(f"/movie/{movie_id}/credits")
            credits = TMDBCredits(**credits_data)
            
            # Get videos (trailers)
            try:
                videos_data = await self._make_request(f"/movie/{movie_id}/videos")
                videos = TMDBVideosResponse(**videos_data)
                trailer_url = None
                
                # Find YouTube trailer
                for video in videos.results:
                    if video.site == "YouTube" and video.type == "Trailer":
                        trailer_url = f"https://www.youtube.com/watch?v={video.key}"
                        break
            except Exception as e:
                logger.warning(f"Could not fetch videos for movie {movie_id}: {e}")
                trailer_url = None
            
            # Convert to internal model
            movie = MovieDetailed(
                id=tmdb_movie.id,
                title=tmdb_movie.title,
                original_title=tmdb_movie.original_title,
                overview=tmdb_movie.overview,
                tagline=tmdb_movie.tagline,
                release_date=datetime.strptime(tmdb_movie.release_date, "%Y-%m-%d").date() 
                           if tmdb_movie.release_date else None,
                runtime=tmdb_movie.runtime,
                poster_path=tmdb_movie.poster_path,
                backdrop_path=tmdb_movie.backdrop_path,
                adult=tmdb_movie.adult,
                original_language=tmdb_movie.original_language,
                popularity=tmdb_movie.popularity,
                vote_average=tmdb_movie.vote_average,
                vote_count=tmdb_movie.vote_count,
                budget=tmdb_movie.budget,
                revenue=tmdb_movie.revenue,
                homepage=tmdb_movie.homepage,
                status=tmdb_movie.status,
                trailer_url=trailer_url,
                poster_url=f"{self.image_base_url}/w500{tmdb_movie.poster_path}" 
                          if tmdb_movie.poster_path else None,
                backdrop_url=f"{self.image_base_url}/w1280{tmdb_movie.backdrop_path}" 
                            if tmdb_movie.backdrop_path else None,
                year=datetime.strptime(tmdb_movie.release_date, "%Y-%m-%d").year 
                     if tmdb_movie.release_date else None,
                genres=[Genre(id=g.id, name=g.name) for g in tmdb_movie.genres],
                cast=[{
                    "id": cast.id,
                    "name": cast.name,
                    "character": cast.character,
                    "profile_path": cast.profile_path,
                    "order": cast.order
                } for cast in credits.cast[:10]],  # Limit to top 10
                crew=[{
                    "id": crew.id,
                    "name": crew.name,
                    "job": crew.job,
                    "department": crew.department,
                    "profile_path": crew.profile_path
                } for crew in credits.crew if crew.job in ["Director", "Producer", "Writer"]],
                created_at=datetime.utcnow()
            )
            
            return movie
            
        except Exception as e:
            logger.error(f"Error fetching movie details for ID {movie_id}: {e}")
            return None
    
    async def search_movies(
        self, 
        query: str, 
        page: int = 1, 
        include_adult: bool = False,
        year: Optional[int] = None
    ) -> MovieList:
        """Search for movies"""
        try:
            params = {
                "query": query,
                "page": page,
                "include_adult": include_adult
            }
            
            if year:
                params["year"] = year
            
            data = await self._make_request("/search/movie", params)
            search_response = TMDBSearchResponse(**data)
            
            # Convert to internal models
            movies = [
                self._convert_tmdb_movie_to_movie(tmdb_movie) 
                for tmdb_movie in search_response.results
            ]
            
            return MovieList(
                movies=movies,
                total=search_response.total_results,
                page=search_response.page,
                page_size=len(movies),
                total_pages=search_response.total_pages,
                has_next=search_response.page < search_response.total_pages,
                has_prev=search_response.page > 1
            )
            
        except Exception as e:
            logger.error(f"Error searching movies with query '{query}': {e}")
            raise
    
    async def discover_movies(self, filters: MovieFilters, page: int = 1) -> MovieList:
        """Discover movies with filters"""
        try:
            params = {"page": page}
            
            # Apply filters
            if filters.genres:
                params["with_genres"] = ",".join(map(str, filters.genres))
            
            if filters.release_year_min:
                params["release_date.gte"] = f"{filters.release_year_min}-01-01"
            
            if filters.release_year_max:
                params["release_date.lte"] = f"{filters.release_year_max}-12-31"
            
            if filters.rating_min:
                params["vote_average.gte"] = filters.rating_min
            if filters.rating_max:
                params["vote_average.lte"] = filters.rating_max
            
            if filters.runtime_min:
                params["with_runtime.gte"] = filters.runtime_min
            
            if filters.runtime_max:
                params["with_runtime.lte"] = filters.runtime_max
            
            if filters.language:
                params["with_original_language"] = filters.language
            
            if filters.include_adult is not None:
                params["include_adult"] = filters.include_adult
            
            # Sort options
            sort_mapping = {
                "popularity": "popularity.desc" if filters.sort_order == "desc" else "popularity.asc",
                "rating": "vote_average.desc" if filters.sort_order == "desc" else "vote_average.asc",
                "release_date": "release_date.desc" if filters.sort_order == "desc" else "release_date.asc",
                "title": "original_title.desc" if filters.sort_order == "desc" else "original_title.asc"
            }
            
            params["sort_by"] = sort_mapping.get(filters.sort_by, "popularity.desc")
            
            data = await self._make_request("/discover/movie", params)
            discover_response = TMDBDiscoverResponse(**data)
            
            # Convert to internal models
            movies = [
                self._convert_tmdb_movie_to_movie(tmdb_movie) 
                for tmdb_movie in discover_response.results
            ]
            
            return MovieList(
                movies=movies,
                total=discover_response.total_results,
                page=discover_response.page,
                page_size=len(movies),
                total_pages=discover_response.total_pages,
                has_next=discover_response.page < discover_response.total_pages,
                has_prev=discover_response.page > 1
            )
            
        except Exception as e:
            logger.error(f"Error discovering movies with filters: {e}")
            raise
    
    async def get_trending_movies(self, time_window: str = "day") -> List[Movie]:
        """Get trending movies"""
        try:
            data = await self._make_request(f"/trending/movie/{time_window}")
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data[:20]:  # Limit to top 20
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching trending movies: {e}")
            raise
    
    async def get_popular_movies(self, page: int = 1) -> List[Movie]:
        """Get popular movies"""
        try:
            data = await self._make_request("/movie/popular", {"page": page})
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data:
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching popular movies: {e}")
            raise
    
    async def get_now_playing(self, page: int = 1) -> List[Movie]:
        """Get now playing movies"""
        try:
            data = await self._make_request("/movie/now_playing", {"page": page})
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data:
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching now playing movies: {e}")
            raise
    
    async def get_upcoming(self, page: int = 1) -> List[Movie]:
        """Get upcoming movies"""
        try:
            data = await self._make_request("/movie/upcoming", {"page": page})
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data:
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching upcoming movies: {e}")
            raise
    
    async def get_top_rated(self, page: int = 1) -> List[Movie]:
        """Get top rated movies"""
        try:
            data = await self._make_request("/movie/top_rated", {"page": page})
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data:
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching top rated movies: {e}")
            raise
    
    async def get_similar_movies(self, movie_id: int, limit: int = 10) -> List[Movie]:
        """Get movies similar to the given movie"""
        try:
            data = await self._make_request(f"/movie/{movie_id}/similar")
            movies_data = data.get("results", [])
            
            movies = []
            for movie_data in movies_data[:limit]:
                tmdb_movie = TMDBMovie(**movie_data)
                movie = self._convert_tmdb_movie_to_movie(tmdb_movie)
                movies.append(movie)
            
            return movies
            
        except Exception as e:
            logger.error(f"Error fetching similar movies for ID {movie_id}: {e}")
            raise
    
    async def get_movie_credits(self, movie_id: int) -> Dict[str, Any]:
        """Get movie cast and crew"""
        try:
            data = await self._make_request(f"/movie/{movie_id}/credits")
            credits = TMDBCredits(**data)
            
            return {
                "cast": [{
                    "id": cast.id,
                    "name": cast.name,
                    "character": cast.character,
                    "profile_path": cast.profile_path,
                    "order": cast.order
                } for cast in credits.cast],
                "crew": [{
                    "id": crew.id,
                    "name": crew.name,
                    "job": crew.job,
                    "department": crew.department,
                    "profile_path": crew.profile_path
                } for crew in credits.crew]
            }
            
        except Exception as e:
            logger.error(f"Error fetching credits for movie ID {movie_id}: {e}")
            raise
    
    async def get_movie_genres(self) -> List[Genre]:
        """Get list of movie genres"""
        try:
            data = await self._make_request("/genre/movie/list")
            genres_data = data.get("genres", [])
            
            genres = []
            for genre_data in genres_data:
                tmdb_genre = TMDBGenre(**genre_data)
                genre = Genre(id=tmdb_genre.id, name=tmdb_genre.name)
                genres.append(genre)
            
            return genres
            
        except Exception as e:
            logger.error(f"Error fetching movie genres: {e}")
            raise
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.aclose()
            self.session = None            
            