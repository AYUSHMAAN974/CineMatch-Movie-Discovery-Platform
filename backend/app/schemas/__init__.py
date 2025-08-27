"""
Pydantic schemas for request/response validation
"""
from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserInDB, User, 
    UserPreferencesUpdate, UserProfile
)
from app.schemas.movie import (
    MovieBase, Movie, MovieCreate, MovieUpdate,
    Genre, MovieWithGenres, MovieSearch, MovieList
)
from app.schemas.rating import (
    RatingBase, RatingCreate, RatingUpdate, Rating,
    ReviewBase, ReviewCreate, Review, WatchlistItem
)
from app.schemas.auth import (
    Token, TokenPayload, Login, Register, 
    PasswordReset, PasswordResetConfirm
)

__all__ = [
    # User schemas
    "UserBase", "UserCreate", "UserUpdate", "UserInDB", "User",
    "UserPreferencesUpdate", "UserProfile",
    
    # Movie schemas
    "MovieBase", "Movie", "MovieCreate", "MovieUpdate",
    "Genre", "MovieWithGenres", "MovieSearch", "MovieList",
    
    # Rating schemas
    "RatingBase", "RatingCreate", "RatingUpdate", "Rating",
    "ReviewBase", "ReviewCreate", "Review", "WatchlistItem",
    
    # Auth schemas
    "Token", "TokenPayload", "Login", "Register",
    "PasswordReset", "PasswordResetConfirm"
]