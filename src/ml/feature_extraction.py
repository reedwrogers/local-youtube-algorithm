import re
from datetime import datetime, timezone
from typing import Dict, Tuple

def calculate_basic_video_metrics(video: Dict) -> Tuple:
    title_length = len(video['title'])
    description_length = len(video['description'])
    view_like_ratio = video['like_count'] / max(video['view_count'], 1)
    engagement_score = (video['like_count'] + video['comment_count']) / max(video['view_count'], 1)

    return (title_length, description_length, view_like_ratio, engagement_score)

def detect_keyword_features_in_video(title: str, description: str) -> Tuple:
    tutorial_keywords = ['tutorial', 'learn', 'course', 'guide', 'how to']
    time_keywords = ['24 hours', '1 day', '1 hour', 'minutes', 'seconds', 'crash course']
    beginner_keywords = ['beginner', 'start', 'basics', 'introduction', 'getting started']
    ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'neural network']
    challenge_keywords = ['challenge', 'build', 'create', 'project', 'coding']

    has_tutorial = any(kw in title or kw in description for kw in tutorial_keywords)
    has_time_constraint = any(kw in title for kw in time_keywords)
    has_beginner = any(kw in title or kw in description for kw in beginner_keywords)
    has_ai = any(kw in title or kw in description for kw in ai_keywords)
    has_challenge = any(kw in title for kw in challenge_keywords)

    return (has_tutorial, has_time_constraint, has_beginner, has_ai, has_challenge)

def calculate_title_sentiment_score(title: str) -> float:
    positive_words = ['amazing', 'best', 'awesome', 'great', 'perfect', 'love', 'incredible']
    negative_words = ['hard', 'difficult', 'impossible', 'failed', 'broke', 'wrong']

    positive_count = sum(1 for word in positive_words if word in title)
    negative_count = sum(1 for word in negative_words if word in title)
    return positive_count - negative_count

def calculate_duration_seconds(video: Dict) -> int:
    """Parse ISO 8601 duration (PT1H2M30S) to total seconds."""
    duration = video.get('duration', '')
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def calculate_video_age_days(video: Dict) -> int:
    """Calculate how many days ago the video was published."""
    published = video.get('published_at', '')
    if not published:
        return 0
    try:
        pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return (now - pub_date).days
    except (ValueError, AttributeError):
        return 0

def calculate_tag_count(video: Dict) -> int:
    """Count the number of tags on the video."""
    tags = video.get('tags', '')
    if not tags:
        return 0
    try:
        import json
        tag_list = json.loads(tags)
        return len(tag_list)
    except (json.JSONDecodeError, TypeError):
        return 0

def extract_all_features_from_video(video: Dict) -> Tuple:
    title = video['title'].lower()
    description = video['description'].lower()

    basic_metrics = calculate_basic_video_metrics(video)
    keyword_features = detect_keyword_features_in_video(title, description)
    sentiment_score = calculate_title_sentiment_score(title)

    # New features
    duration_seconds = calculate_duration_seconds(video)
    video_age_days = calculate_video_age_days(video)
    tag_count = calculate_tag_count(video)
    category_id = video.get('category_id', 0)

    return basic_metrics + keyword_features + (sentiment_score, duration_seconds, video_age_days, tag_count, category_id)