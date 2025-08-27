"""
Helper utility functions
"""
import re
import hashlib
import secrets
import string
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def generate_random_string(length: int = 8) -> str:
    """Generate a random string of specified length"""
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def generate_invitation_code(length: int = 8) -> str:
    """Generate a random invitation code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> bool:
    """Validate username format"""
    # Username should be 3-50 characters, alphanumeric with underscores/hyphens
    pattern = r'^[a-zA-Z0-9_-]{3,50}$'
    return re.match(pattern, username) is not None


def sanitize_search_query(query: str) -> str:
    """Sanitize search query"""
    # Remove special characters that could be problematic
    sanitized = re.sub(r'[<>"\';\\]', '', query)
    return sanitized.strip()


def calculate_pagination_info(
    total_items: int,
    page: int,
    page_size: int
) -> Dict[str, Any]:
    """Calculate pagination information"""
    total_pages = (total_items + page_size - 1) // page_size
    
    return {
        'total': total_items,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'has_next': page < total_pages,
        'has_prev': page > 1
    }


def format_runtime(minutes: Optional[int]) -> Optional[str]:
    """Format runtime in minutes to human readable format"""
    if not minutes:
        return None
    
    hours = minutes // 60
    mins = minutes % 60
    
    if hours > 0:
        return f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
    else:
        return f"{mins}m"


def format_currency(amount: Optional[int]) -> Optional[str]:
    """Format currency amount"""
    if not amount:
        return None
    
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.1f}B"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.1f}K"
    else:
        return f"${amount}"


def extract_year_from_date(date_str: Optional[str]) -> Optional[int]:
    """Extract year from date string"""
    if not date_str:
        return None
    
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).year
    except (ValueError, AttributeError):
        return None


def calculate_age_rating_from_adult(adult: bool) -> str:
    """Calculate age rating from adult flag"""
    return "R" if adult else "PG-13"


def normalize_rating(rating: float, from_scale: float = 10.0, to_scale: float = 5.0) -> float:
    """Normalize rating from one scale to another"""
    return (rating / from_scale) * to_scale


def calculate_confidence_score(factors: List[float]) -> float:
    """Calculate confidence score from multiple factors"""
    if not factors:
        return 0.0
    
    # Use weighted average with diminishing returns
    weights = [1.0 / (i + 1) for i in range(len(factors))]
    weighted_sum = sum(f * w for f, w in zip(factors, weights))
    weight_sum = sum(weights)
    
    return min(weighted_sum / weight_sum, 1.0) if weight_sum > 0 else 0.0


def hash_text(text: str) -> str:
    """Create hash of text"""
    return hashlib.sha256(text.encode()).hexdigest()


def truncate_text(text: str, max_length: int = 150, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)].rstrip() + suffix


def clean_movie_title(title: str) -> str:
    """Clean movie title for better matching"""
    # Remove year in parentheses
    title = re.sub(r'\s*$\d{4}$', '', title)
    
    # Remove articles at the beginning for better sorting
    title = re.sub(r'^(The|A|An)\s+', '', title, flags=re.IGNORECASE)
    
    return title.strip()


def calculate_similarity_score(text1: str, text2: str) -> float:
    """Calculate simple text similarity score"""
    if not text1 or not text2:
        return 0.0
    
    # Simple Jaccard similarity
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0


def format_list_to_string(items: List[str], max_items: int = 3) -> str:
    """Format list to readable string"""
    if not items:
        return ""
    
    if len(items) <= max_items:
        return ", ".join(items)
    else:
        return f"{', '.join(items[:max_items])}, and {len(items) - max_items} more"


def is_recent_date(date: datetime, days: int = 30) -> bool:
    """Check if date is within recent days"""
    if not date:
        return False
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    return date >= cutoff


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers"""
    return numerator / denominator if denominator != 0 else default


def merge_dicts_with_sum(dict1: Dict[str, float], dict2: Dict[str, float]) -> Dict[str, float]:
    """Merge two dictionaries by summing values"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        result[key] = result.get(key, 0) + value
    
    return result


def get_season_from_date(date: datetime) -> str:
    """Get season from date"""
    month = date.month
    
    if month in [12, 1, 2]:
        return "winter"
    elif month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    else:
        return "fall"


def validate_sort_params(sort_by: str, allowed_fields: List[str]) -> str:
    """Validate sort parameters"""
    return sort_by if sort_by in allowed_fields else allowed_fields[0]


def create_cache_key(*args, **kwargs) -> str:
    """Create cache key from arguments"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    return ":".join(key_parts)