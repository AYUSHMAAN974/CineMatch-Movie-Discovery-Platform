"""
Service for handling movie ratings, reviews, and watchlists
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, asc, func, and_
from datetime import datetime
import logging
import uuid

from app.models.rating import Rating, Review, ReviewHelpful, WatchlistItem
from app.models.movie import Movie
from app.models.user import User
from app.schemas.rating import (
    RatingCreate, RatingUpdate, Rating as RatingSchema,
    ReviewCreate, ReviewUpdate, Review as ReviewSchema, ReviewList,
    WatchlistItemCreate, WatchlistItemUpdate, 
    WatchlistItem as WatchlistItemSchema, WatchlistResponse,
    RatingStats, UserRatingsResponse
)

logger = logging.getLogger(__name__)


class RatingService:
    """Service for handling ratings, reviews, and watchlists"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # Rating methods
    def create_rating(self, user_id: uuid.UUID, rating_data: RatingCreate) -> Rating:
        """Create a new movie rating"""
        try:
            db_rating = Rating(
                user_id=user_id,
                movie_id=rating_data.movie_id,
                rating=rating_data.rating,
                is_favorite=rating_data.is_favorite,
                is_watchlist=rating_data.is_watchlist,
                rating_context=rating_data.rating_context,
                mood_when_watched=rating_data.mood_when_watched,
                watched_date=rating_data.watched_date or datetime.utcnow()
            )
            
            self.db.add(db_rating)
            self.db.commit()
            self.db.refresh(db_rating)
            
            logger.info(f"Rating created: User {user_id} rated movie {rating_data.movie_id}")
            return db_rating
            
        except Exception as e:
            logger.error(f"Error creating rating: {e}")
            self.db.rollback()
            raise
    
    def get_rating_by_id(self, rating_id: str) -> Optional[Rating]:
        """Get rating by ID"""
        try:
            return self.db.query(Rating).filter(
                Rating.id == uuid.UUID(rating_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching rating {rating_id}: {e}")
            return None
    
    def get_user_movie_rating(self, user_id: uuid.UUID, movie_id: int) -> Optional[Rating]:
        """Get user's rating for a specific movie"""
        try:
            return self.db.query(Rating).filter(
                and_(Rating.user_id == user_id, Rating.movie_id == movie_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching user rating: {e}")
            return None
    
    def update_rating(self, rating_id: str, rating_update: RatingUpdate) -> Rating:
        """Update an existing rating"""
        try:
            rating = self.get_rating_by_id(rating_id)
            if not rating:
                raise ValueError("Rating not found")
            
            update_data = rating_update.dict(exclude_unset=True)
            
            for field, value in update_data.items():
                if hasattr(rating, field):
                    setattr(rating, field, value)
            
            rating.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(rating)
            
            return rating
            
        except Exception as e:
            logger.error(f"Error updating rating {rating_id}: {e}")
            self.db.rollback()
            raise
    
    def delete_rating(self, rating_id: str) -> bool:
        """Delete a rating"""
        try:
            rating = self.get_rating_by_id(rating_id)
            if not rating:
                return False
            
            self.db.delete(rating)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting rating {rating_id}: {e}")
            self.db.rollback()
            raise
    
    def get_user_ratings(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> UserRatingsResponse:
        """Get user's ratings with pagination"""
        try:
            # Build query
            query = self.db.query(Rating).options(
                joinedload(Rating.movie)
            ).filter(Rating.user_id == user_id)
            
            # Apply sorting
            sort_column = getattr(Rating, sort_by, Rating.created_at)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            ratings = query.offset(offset).limit(page_size).all()
            
            # Convert to schemas
            rating_schemas = []
            for rating in ratings:
                rating_schema = RatingSchema(
                    id=rating.id,
                    user_id=rating.user_id,
                    movie_id=rating.movie_id,
                    rating=rating.rating,
                    is_favorite=rating.is_favorite,
                    is_watchlist=rating.is_watchlist,
                    rating_context=rating.rating_context,
                    mood_when_watched=rating.mood_when_watched,
                    watched_date=rating.watched_date,
                    created_at=rating.created_at,
                    updated_at=rating.updated_at,
                    movie_title=rating.movie.title if rating.movie else None
                )
                rating_schemas.append(rating_schema)
            
            # Calculate stats
            stats = self.get_user_rating_stats(user_id)
            
            return UserRatingsResponse(
                ratings=rating_schemas,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
                has_next=page * page_size < total,
                has_prev=page > 1,
                stats=stats
            )
            
        except Exception as e:
            logger.error(f"Error fetching user ratings: {e}")
            raise
    
    def get_user_rating_stats(self, user_id: uuid.UUID) -> RatingStats:
        """Get user's rating statistics"""
        try:
            # Basic stats
            ratings_query = self.db.query(Rating).filter(Rating.user_id == user_id)
            total_ratings = ratings_query.count()
            
            if total_ratings == 0:
                return RatingStats()
            
            # Average rating
            avg_rating = self.db.query(func.avg(Rating.rating)).filter(
                Rating.user_id == user_id
            ).scalar() or 0.0
            
            # Rating distribution
            rating_dist = self.db.query(
                Rating.rating,
                func.count(Rating.rating)
            ).filter(Rating.user_id == user_id).group_by(Rating.rating).all()
            
            rating_distribution = {str(rating): count for rating, count in rating_dist}
            
            # Favorite genres (based on rated movies)
            favorite_genres_query = self.db.query(
                func.unnest(Movie.genres),
                func.avg(Rating.rating).label('avg_rating'),
                func.count(Rating.id).label('rating_count')
            ).join(Rating, Movie.id == Rating.movie_id).filter(
                Rating.user_id == user_id
            ).group_by(func.unnest(Movie.genres)).having(
                func.count(Rating.id) >= 3  # At least 3 ratings
            ).order_by(desc('avg_rating')).limit(5).all()
            
            favorite_genres = [
                {"genre": genre, "avg_rating": float(avg_rating), "count": count}
                for genre, avg_rating, count in favorite_genres_query
            ]
            
            # Most rated year
            most_rated_year = self.db.query(
                func.extract('year', Movie.release_date).label('year'),
                func.count(Rating.id).label('count')
            ).join(Rating, Movie.id == Rating.movie_id).filter(
                Rating.user_id == user_id,
                Movie.release_date.isnot(None)
            ).group_by('year').order_by(desc('count')).first()
            
            return RatingStats(
                total_ratings=total_ratings,
                average_rating=round(float(avg_rating), 2),
                rating_distribution=rating_distribution,
                favorite_genres=favorite_genres,
                most_rated_year=int(most_rated_year.year) if most_rated_year else None
            )
            
        except Exception as e:
            logger.error(f"Error calculating rating stats for user {user_id}: {e}")
            return RatingStats()
    
    # Review methods
    def create_review(self, user_id: uuid.UUID, review_data: ReviewCreate) -> Review:
        """Create a new movie review"""
        try:
            db_review = Review(
                user_id=user_id,
                movie_id=review_data.movie_id,
                title=review_data.title,
                content=review_data.content,
                rating=review_data.rating,
                is_spoiler=review_data.is_spoiler,
                is_recommended=review_data.is_recommended
            )
            
            self.db.add(db_review)
            self.db.commit()
            self.db.refresh(db_review)
            
            logger.info(f"Review created: User {user_id} reviewed movie {review_data.movie_id}")
            return db_review
            
        except Exception as e:
            logger.error(f"Error creating review: {e}")
            self.db.rollback()
            raise
    
    def get_review_by_id(self, review_id: str) -> Optional[Review]:
        """Get review by ID"""
        try:
            return self.db.query(Review).filter(
                Review.id == uuid.UUID(review_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching review {review_id}: {e}")
            return None
    
    def get_user_movie_review(self, user_id: uuid.UUID, movie_id: int) -> Optional[Review]:
        """Get user's review for a specific movie"""
        try:
            return self.db.query(Review).filter(
                and_(Review.user_id == user_id, Review.movie_id == movie_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching user review: {e}")
            return None
    
    def get_movie_reviews(
        self,
        movie_id: int,
        page: int = 1,
        page_size: int = 10,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        current_user_id: Optional[uuid.UUID] = None
    ) -> ReviewList:
        """Get reviews for a specific movie"""
        try:
            # Build query
            query = self.db.query(Review).options(
                joinedload(Review.user),
                joinedload(Review.movie)
            ).filter(
                Review.movie_id == movie_id,
                Review.is_approved == True
            )
            
            # Apply sorting
            sort_column = getattr(Review, sort_by, Review.created_at)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            reviews = query.offset(offset).limit(page_size).all()
            
            # Convert to schemas
            review_schemas = []
            for review in reviews:
                # Get user's helpful vote if logged in
                user_helpful_vote = None
                if current_user_id:
                    helpful_vote = self.db.query(ReviewHelpful).filter(
                        and_(
                            ReviewHelpful.review_id == review.id,
                            ReviewHelpful.user_id == current_user_id
                        )
                    ).first()
                    user_helpful_vote = helpful_vote.is_helpful if helpful_vote else None
                
                review_schema = ReviewSchema(
                    id=review.id,
                    user_id=review.user_id,
                    movie_id=review.movie_id,
                    title=review.title,
                    content=review.content,
                    rating=review.rating,
                    is_spoiler=review.is_spoiler,
                    is_recommended=review.is_recommended,
                    helpful_count=review.helpful_count,
                    report_count=review.report_count,
                    is_approved=review.is_approved,
                    is_featured=review.is_featured,
                    sentiment_score=review.sentiment_score,
                    emotion_tags=review.emotion_tags.split(",") if review.emotion_tags else None,
                    spoiler_probability=review.spoiler_probability,
                    created_at=review.created_at,
                    updated_at=review.updated_at,
                    user_username=review.user.username if review.user else None,
                    movie_title=review.movie.title if review.movie else None,
                    user_helpful_vote=user_helpful_vote
                )
                review_schemas.append(review_schema)
            
            return ReviewList(
                reviews=review_schemas,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=(total + page_size - 1) // page_size,
                has_next=page * page_size < total,
                has_prev=page > 1
            )
            
        except Exception as e:
            logger.error(f"Error fetching movie reviews: {e}")
            raise
    
    def vote_review_helpful(self, review_id: str, user_id: uuid.UUID, is_helpful: bool):
        """Vote on whether a review is helpful"""
        try:
            # Check if vote already exists
            existing_vote = self.db.query(ReviewHelpful).filter(
                and_(
                    ReviewHelpful.review_id == uuid.UUID(review_id),
                    ReviewHelpful.user_id == user_id
                )
            ).first()
            
            if existing_vote:
                # Update existing vote
                old_vote = existing_vote.is_helpful
                existing_vote.is_helpful = is_helpful
            else:
                # Create new vote
                vote = ReviewHelpful(
                    review_id=uuid.UUID(review_id),
                    user_id=user_id,
                    is_helpful=is_helpful
                )
                self.db.add(vote)
                old_vote = None
            
            # Update review helpful count
            review = self.get_review_by_id(review_id)
            if review:
                if old_vote is None:
                    # New vote
                    if is_helpful:
                        review.helpful_count += 1
                elif old_vote != is_helpful:
                    # Changed vote
                    if is_helpful:
                        review.helpful_count += 1
                    else:
                        review.helpful_count -= 1
            
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error voting on review {review_id}: {e}")
            self.db.rollback()
            raise
    
    # Watchlist methods
    def add_to_watchlist(self, user_id: uuid.UUID, watchlist_data: WatchlistItemCreate) -> WatchlistItem:
        """Add movie to user's watchlist"""
        try:
            db_item = WatchlistItem(
                user_id=user_id,
                movie_id=watchlist_data.movie_id,
                priority=watchlist_data.priority,
                notes=watchlist_data.notes,
                added_reason=watchlist_data.added_reason
            )
            
            self.db.add(db_item)
            self.db.commit()
            self.db.refresh(db_item)
            
            logger.info(f"Added to watchlist: User {user_id}, Movie {watchlist_data.movie_id}")
            return db_item
            
        except Exception as e:
            logger.error(f"Error adding to watchlist: {e}")
            self.db.rollback()
            raise
    
    def is_in_watchlist(self, user_id: uuid.UUID, movie_id: int) -> bool:
        """Check if movie is in user's watchlist"""
        try:
            item = self.db.query(WatchlistItem).filter(
                and_(
                    WatchlistItem.user_id == user_id,
                    WatchlistItem.movie_id == movie_id,
                    WatchlistItem.is_watched == False
                )
            ).first()
            return item is not None
        except Exception as e:
            logger.error(f"Error checking watchlist: {e}")
            return False
    
    def get_watchlist_item_by_id(self, item_id: str) -> Optional[WatchlistItem]:
        """Get watchlist item by ID"""
        try:
            return self.db.query(WatchlistItem).filter(
                WatchlistItem.id == uuid.UUID(item_id)
            ).first()
        except Exception as e:
            logger.error(f"Error fetching watchlist item {item_id}: {e}")
            return None
    
    def get_user_watchlist(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        watched: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> WatchlistResponse:
        """Get user's watchlist with pagination"""
        try:
            # Build query
            query = self.db.query(WatchlistItem).options(
                joinedload(WatchlistItem.movie)
            ).filter(WatchlistItem.user_id == user_id)
            
            # Filter by watched status if specified
            if watched is not None:
                query = query.filter(WatchlistItem.is_watched == watched)
            
            # Apply sorting
            sort_column = getattr(WatchlistItem, sort_by, WatchlistItem.created_at)
            if sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
            
            # Get counts
            total = query.count()
            watched_count = self.db.query(WatchlistItem).filter(
                WatchlistItem.user_id == user_id,
                WatchlistItem.is_watched == True
            ).count()
            unwatched_count = total - watched_count
            
            # Apply pagination
            offset = (page - 1) * page_size
            items = query.offset(offset).limit(page_size).all()
            
            # Convert to schemas
            item_schemas = []
            total_runtime = 0
            
            for item in items:
                movie = item.movie
                item_schema = WatchlistItemSchema(
                    id=item.id,
                    user_id=item.user_id,
                    movie_id=item.movie_id,
                    priority=item.priority,
                    notes=item.notes,
                    added_reason=item.added_reason,
                    is_watched=item.is_watched,
                    watched_date=item.watched_date,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    movie_title=movie.title if movie else None,
                    movie_poster_url=f"{settings.TMDB_IMAGE_BASE_URL}/w500{movie.poster_path}" 
                                    if movie and movie.poster_path else None,
                    movie_year=movie.year if movie else None,
                    movie_genres=[genre.name for genre in movie.genres] if movie else None
                )
                item_schemas.append(item_schema)
                
                # Add to total runtime if unwatched and has runtime
                if not item.is_watched and movie and movie.runtime:
                    total_runtime += movie.runtime
            
            return WatchlistResponse(
                items=item_schemas,
                total=total,
                watched_count=watched_count,
                unwatched_count=unwatched_count,
                total_runtime=total_runtime if total_runtime > 0 else None
            )
            
        except Exception as e:
            logger.error(f"Error fetching user watchlist: {e}")
            raise
    
    def update_watchlist_item(self, item_id: str, update_data: WatchlistItemUpdate) -> WatchlistItem:
        """Update a watchlist item"""
        try:
            item = self.get_watchlist_item_by_id(item_id)
            if not item:
                raise ValueError("Watchlist item not found")
            
            update_fields = update_data.dict(exclude_unset=True)
            
            for field, value in update_fields.items():
                if hasattr(item, field):
                    setattr(item, field, value)
            
            # If marked as watched, set watched_date if not provided
            if update_data.is_watched and not update_data.watched_date and not item.watched_date:
                item.watched_date = datetime.utcnow()
            
            item.updated_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(item)
            
            return item
            
        except Exception as e:
            logger.error(f"Error updating watchlist item {item_id}: {e}")
            self.db.rollback()
            raise
    
    def remove_from_watchlist(self, item_id: str) -> bool:
        """Remove movie from watchlist"""
        try:
            item = self.get_watchlist_item_by_id(item_id)
            if not item:
                return False
            
            self.db.delete(item)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing from watchlist {item_id}: {e}")
            self.db.rollback()
            raise