import sqlite3
from datetime import datetime
from typing import List, Dict

def setup_database_tables(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT,
            description TEXT,
            view_count INTEGER,
            like_count INTEGER,
            comment_count INTEGER,
            duration TEXT,
            published_at TEXT,
            channel_name TEXT,
            thumbnail_url TEXT,
            tags TEXT,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            liked BOOLEAN,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_features (
            video_id TEXT PRIMARY KEY,
            title_length INTEGER,
            description_length INTEGER,
            view_like_ratio REAL,
            engagement_score REAL,
            title_sentiment REAL,
            has_tutorial_keywords BOOLEAN,
            has_time_constraint BOOLEAN,
            has_beginner_keywords BOOLEAN,
            has_ai_keywords BOOLEAN,
            has_challenge_keywords BOOLEAN,
            duration_seconds INTEGER,
            video_age_days INTEGER,
            tag_count INTEGER,
            category_id INTEGER,
            FOREIGN KEY (video_id) REFERENCES videos (id)
        )
    ''')

    # Add new columns if they don't exist (safe for existing DBs)
    for col in ['duration_seconds', 'video_age_days', 'tag_count', 'category_id']:
        try:
            cursor.execute(f'ALTER TABLE video_features ADD COLUMN {col} INTEGER')
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()

    # Backfill features for videos that don't have the new columns populated
    backfill_missing_features(db_path)


def backfill_missing_features(db_path: str):
    """Recompute and save features for existing videos that are missing new feature columns."""
    import json
    import re
    from datetime import datetime, timezone

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get videos that need backfilling (where new feature columns are NULL)
    cursor.execute('''
        SELECT v.id, v.title, v.description, v.view_count, v.like_count, v.comment_count,
               v.duration, v.published_at, v.channel_name, v.thumbnail_url, v.tags, v.category_id
        FROM videos v
        LEFT JOIN video_features vf ON v.id = vf.video_id
        WHERE vf.video_id IS NULL OR vf.duration_seconds IS NULL
    ''')
    rows = cursor.fetchall()

    for row in rows:
        video = {
            'id': row[0], 'title': row[1], 'description': row[2],
            'view_count': row[3], 'like_count': row[4], 'comment_count': row[5],
            'duration': row[6], 'published_at': row[7], 'channel_name': row[8],
            'thumbnail_url': row[9], 'tags': row[10], 'category_id': row[11],
        }

        title = video['title'].lower()
        description = video['description'].lower()

        # Basic metrics
        title_length = len(video['title'])
        description_length = len(video['description'])
        view_like_ratio = video['like_count'] / max(video['view_count'], 1)
        engagement_score = (video['like_count'] + video['comment_count']) / max(video['view_count'], 1)

        # Keyword features
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

        # Sentiment
        positive_words = ['amazing', 'best', 'awesome', 'great', 'perfect', 'love', 'incredible']
        negative_words = ['hard', 'difficult', 'impossible', 'failed', 'broke', 'wrong']
        sentiment_score = sum(1 for w in positive_words if w in title) - sum(1 for w in negative_words if w in title)

        # New features
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', video.get('duration', ''))
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            duration_seconds = hours * 3600 + minutes * 60 + seconds
        else:
            duration_seconds = 0

        try:
            pub_date = datetime.fromisoformat(video.get('published_at', '').replace('Z', '+00:00'))
            video_age_days = (datetime.now(timezone.utc) - pub_date).days
        except (ValueError, AttributeError):
            video_age_days = 0

        try:
            tag_list = json.loads(video.get('tags', '[]'))
            tag_count = len(tag_list)
        except (json.JSONDecodeError, TypeError):
            tag_count = 0

        category_id = video.get('category_id', 0) or 0

        cursor.execute('''
            INSERT OR REPLACE INTO video_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            video['id'], title_length, description_length, view_like_ratio, engagement_score,
            sentiment_score, has_tutorial, has_time_constraint, has_beginner, has_ai,
            has_challenge, duration_seconds, video_age_days, tag_count, category_id
        ))

    conn.commit()
    if rows:
        print(f"  Backfilled features for {len(rows)} videos")
    conn.close()
