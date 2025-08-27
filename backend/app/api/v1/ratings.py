"""
Rating and review endpoints
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.models.user import User
from app.schemas.rating import (
    Rating, RatingCreate, RatingUpdate, RatingStats,
    Review, ReviewCreate, ReviewUpdate, ReviewList, ReviewHelpfulVote,
    WatchlistItem, WatchlistItemCreate, WatchlistItemUpdate, WatchlistResponse,
    UserRatingsResponse
)
from app.services.rating_service import RatingService
from app.utils.dependencies import get_current_active_user
from app.tasks.analytics_tasks import track_user_activity
from app.tasks.recommendation_tasks import update_user_taste_profile

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=Rating, status_code=status.HTTP_201_CREATED)
async def create_rating(
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new movie rating
    """
    try:
        rating_service = RatingService(db)
        
        # Check if rating already exists
        existing_rating = rating_service.get_user_movie_rating(
            current_user.id, 
            rating_data.movie_id
        )
        
        if existing_rating:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating already exists for this movie. Use PUT to update."
            )
        
        # Create new rating
        rating = rating_service.create_rating(current_user.id, rating_data)
        
        # Track activity asynchronously
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="rate",
            movie_id=rating_data.movie_id,
            metadata={"rating": rating_data.rating}
        )
        
        # Update user taste profile
        update_user_taste_profile.delay(str(current_user.id))
        
        logger.info(f"Rating created: User {current_user.id} rated movie {rating_data.movie_id}")
        
        return rating
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating rating: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rating"
        )


@router.put("/{rating_id}", response_model=Rating)
async def update_rating(
    rating_id: str,
    rating_data: RatingUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update an existing rating
    """
    try:
        rating_service = RatingService(db)
        
        # Check if rating exists and belongs to user
        existing_rating = rating_service.get_rating_by_id(rating_id)
        
        if not existing_rating:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rating not found"
            )
        
        if existing_rating.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update another user's rating"
            )
        
        # Update rating
        updated_rating = rating_service.update_rating(rating_id, rating_data)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="update_rating",
            movie_id=updated_rating.movie_id,
            metadata={"new_rating": rating_data.rating}
        )
        
        # Update taste profile
        update_user_taste_profile.delay(str(current_user.id))
        
        return updated_rating
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating rating: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rating"
        )


@router.delete("/{rating_id}")
async def delete_rating(
    rating_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Delete a rating
    """
    try:
        rating_service = RatingService(db)
        
        # Check if rating exists and belongs to user
        existing_rating = rating_service.get_rating_by_id(rating_id)
        
        if not existing_rating:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rating not found"
            )
        
        if existing_rating.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete another user's rating"
            )
        
        # Delete rating
        rating_service.delete_rating(rating_id)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="delete_rating",
            movie_id=existing_rating.movie_id
        )
        
        # Update taste profile
        update_user_taste_profile.delay(str(current_user.id))
        
        return {"message": "Rating deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting rating: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete rating"
        )


@router.get("/my-ratings", response_model=UserRatingsResponse)
async def get_my_ratings(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", regex="^(created_at|rating|movie_title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get current user's ratings with pagination
    """
    try:
        rating_service = RatingService(db)
        
        # Get ratings
        ratings_response = rating_service.get_user_ratings(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return ratings_response
        
    except Exception as e:
        logger.error(f"Error fetching user ratings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user ratings"
        )


@router.get("/stats", response_model=RatingStats)
async def get_rating_stats(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get current user's rating statistics
    """
    try:
        rating_service = RatingService(db)
        stats = rating_service.get_user_rating_stats(current_user.id)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching rating stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch rating statistics"
        )


# Review endpoints
@router.post("/reviews", response_model=Review, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Create a new movie review
    """
    try:
        rating_service = RatingService(db)
        
        # Check if review already exists
        existing_review = rating_service.get_user_movie_review(
            current_user.id, 
            review_data.movie_id
        )
        
        if existing_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review already exists for this movie. Use PUT to update."
            )
        
        # Create review
        review = rating_service.create_review(current_user.id, review_data)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="review",
            movie_id=review_data.movie_id,
            metadata={"review_length": len(review_data.content)}
        )
        
        # Trigger sentiment analysis
        from app.tasks.recommendation_tasks import analyze_review_sentiment
        analyze_review_sentiment.delay(str(review.id))
        
        return review
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create review"
        )


@router.get("/reviews/movie/{movie_id}", response_model=ReviewList)
async def get_movie_reviews(
    movie_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=50, description="Items per page"),
    sort_by: str = Query("created_at", regex="^(created_at|helpful_count|rating)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get reviews for a specific movie
    """
    try:
        rating_service = RatingService(db)
        
        reviews_response = rating_service.get_movie_reviews(
            movie_id=movie_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            current_user_id=current_user.id if current_user else None
        )
        
        return reviews_response
        
    except Exception as e:
        logger.error(f"Error fetching movie reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch movie reviews"
        )


@router.post("/reviews/{review_id}/helpful", status_code=status.HTTP_204_NO_CONTENT)
async def vote_review_helpful(
    review_id: str,
    vote_data: ReviewHelpfulVote,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> None:  # Change return type to None
    """
    Vote on whether a review is helpful
    """
    try:
        rating_service = RatingService(db)
        
        # Check if review exists
        review = rating_service.get_review_by_id(review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        # Can't vote on own review
        if review.user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot vote on your own review"
            )
        
        # Create or update helpful vote
        rating_service.vote_review_helpful(
            review_id, 
            current_user.id, 
            vote_data.is_helpful
        )
        
        # ✅ Don't return anything for 204
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error voting on review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to vote on review"
        )


# Watchlist endpoints
@router.post("/watchlist", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    watchlist_data: WatchlistItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Add movie to user's watchlist
    """
    try:
        rating_service = RatingService(db)
        
        # Check if already in watchlist
        if rating_service.is_in_watchlist(current_user.id, watchlist_data.movie_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Movie already in watchlist"
            )
        
        # Add to watchlist
        watchlist_item = rating_service.add_to_watchlist(current_user.id, watchlist_data)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="add_watchlist",
            movie_id=watchlist_data.movie_id
        )
        
        return watchlist_item
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add to watchlist"
        )


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    watched: Optional[bool] = Query(None, description="Filter by watched status"),
    sort_by: str = Query("created_at", regex="^(created_at|priority|movie_title)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Get user's watchlist
    """
    try:
        rating_service = RatingService(db)
        
        watchlist_response = rating_service.get_user_watchlist(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            watched=watched,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        return watchlist_response
        
    except Exception as e:
        logger.error(f"Error fetching watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch watchlist"
        )


@router.put("/watchlist/{item_id}", response_model=WatchlistItem)
async def update_watchlist_item(
    item_id: str,
    update_data: WatchlistItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Update a watchlist item
    """
    try:
        rating_service = RatingService(db)
        
        # Check if item exists and belongs to user
        item = rating_service.get_watchlist_item_by_id(item_id)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist item not found"
            )
        
        if item.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update another user's watchlist item"
            )
        
        # Update item
        updated_item = rating_service.update_watchlist_item(item_id, update_data)
        
        # Track if marked as watched
        if update_data.is_watched is True and not item.is_watched:
            track_user_activity.delay(
                user_id=str(current_user.id),
                activity_type="watched",
                movie_id=item.movie_id
            )
        
        return updated_item
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating watchlist item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update watchlist item"
        )


@router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Remove movie from watchlist
    """
    try:
        rating_service = RatingService(db)
        
        # Check if item exists and belongs to user
        item = rating_service.get_watchlist_item_by_id(item_id)
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist item not found"
            )
        
        if item.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot remove another user's watchlist item"
            )
        
        # Remove item
        rating_service.remove_from_watchlist(item_id)
        
        # Track activity
        track_user_activity.delay(
            user_id=str(current_user.id),
            activity_type="remove_watchlist",
            movie_id=item.movie_id
        )
        
        return {"message": "Removed from watchlist successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove from watchlist"
        )