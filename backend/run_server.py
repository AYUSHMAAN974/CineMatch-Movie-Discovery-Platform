"""
Development server runner for CineMatch
"""
import uvicorn
import sys
import os
import logging

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the development server"""
    logger.info(f"Starting {settings.PROJECT_NAME} development server...")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API Documentation: http://localhost:8000{settings.API_V1_STR}/docs")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        reload_dirs=["app"] if settings.DEBUG else None,
    )


if __name__ == "__main__":
    main()