"""
Database configuration and session management
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Database engine configuration
engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "echo": settings.DEBUG,
}

# Add connection pooling for production
if not settings.DEBUG:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 0,
    })

# Create database engine
engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# Metadata for migrations
metadata = MetaData()


def get_db() -> Session:
    """
    Database dependency for FastAPI routes
    Yields a database session and ensures it's closed after use
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise


def drop_tables():
    """Drop all tables (use with caution!)"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        raise


# Test database engine for testing
test_engine = None
TestSessionLocal = None

def get_test_db():
    """Get test database session"""
    global test_engine, TestSessionLocal
    
    if settings.TEST_DATABASE_URL:
        if test_engine is None:
            test_engine = create_engine(
                settings.TEST_DATABASE_URL,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
                echo=settings.DEBUG,
            )
            TestSessionLocal = sessionmaker(
                autocommit=False, 
                autoflush=False, 
                bind=test_engine
            )
        
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Fallback to main database if test database not configured
        yield from get_db()