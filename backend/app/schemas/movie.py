"""
Movie-related Pydantic schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, date


class GenreBase(BaseModel):
    """Base genre schema"""
    name: str = Field(..., max_length=100)


class Genre(GenreBase):
    """Genre schema with ID"""
    id: int
    
    class Config:
        from_attributes = True


class GenreCreate(GenreBase):
    """Schema for creating genres"""
    id: int  # TMDB genre ID


class MovieBase(BaseModel):
    """Base movie schema"""
    title: str = Field(..., max_length=500)
    original_title: Optional[str] = Field(None, max_length=500)
    overview: Optional[str] = None
    tagline: Optional[str] = Field(None, max_length=500)
    release_date: Optional[date] = None
    runtime: Optional[int] = Field(None, gt=0, lt=1000)
    original_language: Optional[str] = Field(None, max_length=10)
    adult: bool = False


class MovieCreate(MovieBase):
    """Schema for creating movies"""
    id: int  # TMDB movie ID
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = Field(None, ge=0, le=10)
    vote_count: Optional[int] = Field(None, ge=0)
    popularity: Optional[float] = Field(None, ge=0)
    budget: Optional[int] = Field(None, ge=0)
    revenue: Optional[int] = Field(None, ge=0)
    homepage: Optional[str] = None
    status: Optional[str] = None
    genre_ids: Optional[List[int]] = []


class MovieUpdate(BaseModel):
    """Schema for updating movies"""
    title: Optional[str] = Field(None, max_length=500)
    overview: Optional[str] = None
    tagline: Optional[str] = Field(None, max_length=500)
    runtime: Optional[int] = Field(None, gt=0, lt=1000)
    vote_average: Optional[float] = Field(None, ge=0, le=10)
    vote_count: Optional[int] = Field(None, ge=0)
    popularity: Optional[float] = Field(None, ge=0)
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    trailer_url: Optional[str] = None
    is_active: Optional[bool] = None


class Movie(MovieBase):
    """Complete movie schema for responses"""
    id: int
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    popularity: Optional[float] = None
    genres: Optional[List[Genre]] = []
    year: Optional[int] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    average_rating: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class MovieWithGenres(Movie):
    """Movie schema with detailed genre information"""
    genres: List[Genre] = []


class MovieDetailed(MovieWithGenres):
    """Detailed movie schema with additional information"""
    budget: Optional[int] = None
    revenue: Optional[int] = None
    homepage: Optional[str] = None
    status: Optional[str] = None
    tagline: Optional[str] = None
    trailer_url: Optional[str] = None
    spoken_languages: Optional[List[str]] = None
    production_countries: Optional[List[str]] = None
    cast: Optional[List[Dict[str, Any]]] = []
    crew: Optional[List[Dict[str, Any]]] = []
    similar_movies: Optional[List['Movie']] = []
    user_rating: Optional[float] = None
    is_in_watchlist: Optional[bool] = False


class MovieList(BaseModel):
    """Movie list response schema"""
    movies: List[Movie]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class MovieSearch(BaseModel):
    """Movie search request schema"""
    query: str = Field(..., min_length=1, max_length=200)
    page: Optional[int] = Field(1, ge=1, le=1000)
    include_adult: Optional[bool] = False
    year: Optional[int] = Field(None, ge=1900, le=2030)
    language: Optional[str] = Field(None, max_length=5)


class MovieFilters(BaseModel):
    """Movie filtering schema"""
    genres: Optional[List[int]] = None
    release_year_min: Optional[int] = Field(None, ge=1900, le=2030)
    release_year_max: Optional[int] = Field(None, ge=1900, le=2030)
    rating_min: Optional[float] = Field(None, ge=0, le=10)
    rating_max: Optional[float] = Field(None, ge=0, le=10)
    runtime_min: Optional[int] = Field(None, ge=0, le=1000)
    runtime_max: Optional[int] = Field(None, ge=0, le=1000)
    language: Optional[str] = None
    sort_by: Optional[str] = Field("popularity", pattern="^(popularity|rating|release_date|title)$")
    sort_order: Optional[str] = Field("desc", pattern="^(asc|desc)$")
    include_adult: Optional[bool] = False


class MovieStats(BaseModel):
    """Movie statistics schema"""
    movie_id: int
    view_count: int = 0
    rating_count: int = 0
    review_count: int = 0
    watchlist_count: int = 0
    average_rating: float = 0.0
    rating_distribution: Optional[Dict[str, int]] = None
    recommendation_count: int = 0
    click_through_rate: float = 0.0
    
    class Config:
        from_attributes = True


class MovieCast(BaseModel):
    """Movie cast member schema"""
    person_id: int
    name: str
    character_name: Optional[str] = None
    gender: Optional[int] = None
    order: Optional[int] = None
    profile_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class MovieCrew(BaseModel):
    """Movie crew member schema"""
    person_id: int
    name: str
    job: str
    department: Optional[str] = None
    gender: Optional[int] = None
    profile_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class MovieCollection(BaseModel):
    """Movie collection schema"""
    id: int
    name: str
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    
    class Config:
        from_attributes = True


class TrendingMoviesResponse(BaseModel):
    """Trending movies response schema"""
    trending_today: List[Movie]
    trending_week: List[Movie]
    popular: List[Movie]
    now_playing: List[Movie]
    upcoming: List[Movie]
    top_rated: List[Movie]