"""
Database initialization script
Creates database tables and initial data
"""
import asyncio
import logging
import os
import sys
from sqlalchemy.orm import Session

# Add error handling for configuration loading
try:
    from app.core.database import engine, SessionLocal, create_tables, Base
    from app.core.config import settings
    from app.models import User, Movie, Genre  # Import all models
    from app.services.tmdb.client import TMDBClient
except ImportError as e:
    print(f"Import error: {e}")
    print("Please check your .env file configuration")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database with tables and initial data"""
    try:
        # Check if .env file exists
        env_file = ".env"
        if not os.path.exists(env_file):
            logger.warning(f"{env_file} not found. Using default configuration.")
        
        logger.info("Creating database tables...")
        
        # Create all tables
        create_tables()
        
        logger.info("Database tables created successfully!")
        
        # Initialize with basic data
        db = SessionLocal()
        
        try:
            # Check if we already have data
            existing_genres = db.query(Genre).count()
            
            if existing_genres == 0:
                logger.info("Initializing basic data...")
                asyncio.run(init_basic_data(db))
            else:
                logger.info("Database already has basic data")
                
        finally:
            db.close()
            
        logger.info("Database initialization completed!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check if your .env file exists and is properly formatted")
        print("2. Ensure BACKEND_CORS_ORIGINS is a valid JSON array, e.g.: BACKEND_CORS_ORIGINS=[\"http://localhost:3000\"]")
        print("3. Check database connection settings")
        raise


async def init_basic_data(db: Session):
    """Initialize basic data like genres"""
    try:
        # Initialize TMDB client
        tmdb_client = TMDBClient()
        
        # Fetch and create genres
        logger.info("Fetching genres from TMDB...")
        genres_data = await tmdb_client._make_request("/genre/movie/list")
        
        if genres_data and 'genres' in genres_data:
            for genre_data in genres_data['genres']:
                genre = Genre(
                    id=genre_data['id'],
                    name=genre_data['name']
                )
                db.add(genre)
            
            db.commit()
            logger.info(f"Created {len(genres_data['genres'])} genres")
        
        # Fetch some initial popular movies
        logger.info("Fetching initial popular movies...")
        popular_movies = await tmdb_client.get_popular_movies(page=1)
        
        movie_count = 0
        for movie_data in popular_movies[:20]:  # Get top 20 popular movies
            try:
                # Get detailed movie info
                detailed_movie = await tmdb_client.get_movie_details(movie_data.id)
                
                if detailed_movie:
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
                    
                    # Add genres to movie
                    for genre_data in detailed_movie.genres:
                        genre = db.query(Genre).filter(Genre.id == genre_data.id).first()
                        if genre:
                            movie.genres.append(genre)
                    
                    movie_count += 1
                    
            except Exception as e:
                logger.error(f"Error adding movie {movie_data.id}: {e}")
                continue
        
        db.commit()
        logger.info(f"Created {movie_count} initial movies")
        
        # Create admin user if it doesn't exist
        admin_email = "admin@cinematch.com"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        
        if not existing_admin:
            from app.core.security import security
            
            admin_user = User(
                email=admin_email,
                username="admin",
                hashed_password=security.get_password_hash("admin123"),
                full_name="CineMatch Admin",
                is_active=True,
                is_verified=True,
                is_premium=True
            )
            
            db.add(admin_user)
            db.commit()
            logger.info("Created admin user (admin@cinematch.com / admin123)")
        
        await tmdb_client.close()
        
    except Exception as e:
        logger.error(f"Error initializing basic data: {e}")
        raise


if __name__ == "__main__":
    init_db()