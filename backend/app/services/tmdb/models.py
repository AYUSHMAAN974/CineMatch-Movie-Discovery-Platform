"""
Pydantic models for TMDB API responses
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import date


class TMDBGenre(BaseModel):
    """TMDB Genre model"""
    id: int
    name: str


class TMDBMovie(BaseModel):
    """TMDB Movie model"""
    id: int
    title: str
    original_title: Optional[str] = None
    overview: Optional[str] = None
    release_date: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    adult: bool = False
    genre_ids: List[int] = []
    original_language: Optional[str] = None
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    video: bool = False


class TMDBMovieDetails(TMDBMovie):
    """Extended TMDB Movie model with detailed information"""
    budget: Optional[int] = None
    homepage: Optional[str] = None
    imdb_id: Optional[str] = None
    revenue: Optional[int] = None
    runtime: Optional[int] = None
    status: Optional[str] = None
    tagline: Optional[str] = None
    genres: List[TMDBGenre] = []
    production_companies: List[Dict[str, Any]] = []
    production_countries: List[Dict[str, Any]] = []
    spoken_languages: List[Dict[str, Any]] = []
    belongs_to_collection: Optional[Dict[str, Any]] = None


class TMDBCastMember(BaseModel):
    """TMDB Cast member model"""
    id: int
    name: str
    character: Optional[str] = None
    credit_id: str
    gender: Optional[int] = None
    order: Optional[int] = None
    profile_path: Optional[str] = None


class TMDBCrewMember(BaseModel):
    """TMDB Crew member model"""
    id: int
    name: str
    job: str
    department: str
    credit_id: str
    gender: Optional[int] = None
    profile_path: Optional[str] = None


class TMDBCredits(BaseModel):
    """TMDB Credits model"""
    id: int
    cast: List[TMDBCastMember] = []
    crew: List[TMDBCrewMember] = []


class TMDBSearchResponse(BaseModel):
    """TMDB Search response model"""
    page: int
    results: List[TMDBMovie]
    total_pages: int
    total_results: int


class TMDBDiscoverResponse(BaseModel):
    """TMDB Discover response model"""
    page: int
    results: List[TMDBMovie]
    total_pages: int
    total_results: int


class TMDBVideo(BaseModel):
    """TMDB Video model (trailers, etc.)"""
    id: str
    iso_639_1: str
    iso_3166_1: str
    key: str
    name: str
    official: bool
    published_at: Optional[str] = None
    site: str
    size: int
    type: str


class TMDBVideosResponse(BaseModel):
    """TMDB Videos response model"""
    id: int
    results: List[TMDBVideo] = []


class TMDBReview(BaseModel):
    """TMDB Review model"""
    id: str
    author: str
    author_details: Dict[str, Any] = {}
    content: str
    created_at: str
    updated_at: str
    url: str


class TMDBReviewsResponse(BaseModel):
    """TMDB Reviews response model"""
    id: int
    page: int
    results: List[TMDBReview] = []
    total_pages: int
    total_results: int