"""
Machine learning model training script
Trains and saves all recommendation models
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.config import settings
from app.services.ml.content_based import ContentBasedRecommender
from app.services.ml.collaborative import CollaborativeRecommender
from app.services.ml.mood_analyzer import MoodAnalyzer
from app.ml_models import model_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def train_all_models():
    """Train all recommendation models"""
    db = SessionLocal()
    
    try:
        logger.info("Starting ML model training...")
        
        # Create models directory if it doesn't exist
        os.makedirs(settings.ML_MODEL_PATH, exist_ok=True)
        
        training_results = {}
        
        # 1. Train Content-Based Recommender
        logger.info("Training Content-Based Recommender...")
        try:
            content_recommender = ContentBasedRecommender(db)
            content_success = await content_recommender.train_model()
            training_results['content_based'] = content_success
            
            if content_success:
                logger.info("✓ Content-Based model trained successfully")
            else:
                logger.error("✗ Content-Based model training failed")
                
        except Exception as e:
            logger.error(f"✗ Content-Based model training error: {e}")
            training_results['content_based'] = False
        
        # 2. Train Collaborative Filtering Recommender
        logger.info("Training Collaborative Filtering Recommender...")
        try:
            collaborative_recommender = CollaborativeRecommender(db)
            collaborative_success = await collaborative_recommender.train_model()
            training_results['collaborative'] = collaborative_success
            
            if collaborative_success:
                logger.info("✓ Collaborative Filtering model trained successfully")
            else:
                logger.error("✗ Collaborative Filtering model training failed")
                
        except Exception as e:
            logger.error(f"✗ Collaborative Filtering model training error: {e}")
            training_results['collaborative'] = False
        
        # 3. Train Mood Analyzer
        logger.info("Training Mood Analyzer...")
        try:
            mood_analyzer = MoodAnalyzer(db)
            mood_success = await mood_analyzer.train_model()
            training_results['mood_analyzer'] = mood_success
            
            if mood_success:
                logger.info("✓ Mood Analyzer trained successfully")
            else:
                logger.error("✗ Mood Analyzer training failed")
                
        except Exception as e:
            logger.error(f"✗ Mood Analyzer training error: {e}")
            training_results['mood_analyzer'] = False
        
        # 4. Save training metadata
        training_metadata = {
            'training_date': datetime.utcnow().isoformat(),
            'results': training_results,
            'success_count': sum(training_results.values()),
            'total_models': len(training_results)
        }
        
        model_manager.save_model(
            training_metadata, 
            'training_metadata', 
            version=datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        )
        
        # Summary
        successful_models = sum(training_results.values())
        total_models = len(training_results)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"TRAINING SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"Total models: {total_models}")
        logger.info(f"Successful: {successful_models}")
        logger.info(f"Failed: {total_models - successful_models}")
        logger.info(f"Success rate: {(successful_models/total_models)*100:.1f}%")
        
        for model_name, success in training_results.items():
            status = "✓" if success else "✗"
            logger.info(f"{status} {model_name.replace('_', ' ').title()}")
        
        logger.info(f"{'='*50}")
        
        if successful_models == total_models:
            logger.info("🎉 All models trained successfully!")
            return True
        elif successful_models > 0:
            logger.warning("⚠️  Some models failed to train")
            return False
        else:
            logger.error("❌ All model training failed")
            return False
            
    except Exception as e:
        logger.error(f"Training process failed: {e}")
        return False
        
    finally:
        db.close()


def train_specific_model(model_name: str):
    """Train a specific model"""
    db = SessionLocal()
    
    try:
        logger.info(f"Training {model_name} model...")
        
        if model_name == "content":
            recommender = ContentBasedRecommender(db)
        elif model_name == "collaborative":
            recommender = CollaborativeRecommender(db)
        elif model_name == "mood":
            recommender = MoodAnalyzer(db)
        else:
            logger.error(f"Unknown model: {model_name}")
            return False
        
        success = asyncio.run(recommender.train_model())
        
        if success:
            logger.info(f"✓ {model_name} model trained successfully")
        else:
            logger.error(f"✗ {model_name} model training failed")
            
        return success
        
    except Exception as e:
        logger.error(f"Error training {model_name} model: {e}")
        return False
        
    finally:
        db.close()


def list_available_models():
    """List all available trained models"""
    logger.info("Available trained models:")
    models = model_manager.list_models()
    
    if not models:
        logger.info("No trained models found")
        return
    
    for model in models:
        size_mb = model['size'] / (1024 * 1024)
        logger.info(f"- {model['name']} (v{model['version']}) - {size_mb:.1f}MB - {model['saved_at']}")


def cleanup_old_models():
    """Cleanup old model versions"""
    logger.info("Cleaning up old model versions...")
    deleted_count = model_manager.cleanup_old_models(keep_versions=3)
    logger.info(f"Deleted {deleted_count} old model versions")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='CineMatch ML Model Training')
    parser.add_argument('--model', type=str, help='Train specific model (content, collaborative, mood)')
    parser.add_argument('--list', action='store_true', help='List available models')
    parser.add_argument('--cleanup', action='store_true', help='Cleanup old model versions')
    
    args = parser.parse_args()
    
    if args.list:
        list_available_models()
    elif args.cleanup:
        cleanup_old_models()
    elif args.model:
        success = train_specific_model(args.model)
        sys.exit(0 if success else 1)
    else:
        # Train all models
        success = asyncio.run(train_all_models())
        sys.exit(0 if success else 1)