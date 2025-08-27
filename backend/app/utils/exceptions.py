"""
Custom exceptions for the application
"""
from fastapi import HTTPException, status


class CineMatchException(Exception):
    """Base exception for CineMatch application"""
    pass


class UserNotFound(CineMatchException):
    """User not found exception"""
    pass


class MovieNotFound(CineMatchException):
    """Movie not found exception"""
    pass


class DuplicateRating(CineMatchException):
    """Duplicate rating exception"""
    pass


class InsufficientPermissions(CineMatchException):
    """Insufficient permissions exception"""
    pass


class TMDBAPIError(CineMatchException):
    """TMDB API error"""
    pass


class MLModelError(CineMatchException):
    """Machine learning model error"""
    pass


class CacheError(CineMatchException):
    """Cache operation error"""
    pass


# HTTP Exception mappings
def user_not_found_exception():
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


def movie_not_found_exception():
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Movie not found"
    )


def duplicate_rating_exception():
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Rating already exists for this movie"
    )


def insufficient_permissions_exception():
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions"
    )


def tmdb_api_error_exception():
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Movie database service temporarily unavailable"
    )


def ml_model_error_exception():
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Recommendation service temporarily unavailable"
    )