import sqlite3
import pandas as pd

def save_video_rating_to_database(video_id: str, liked: bool, notes: str, db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO preferences (video_id, liked, notes) VALUES (?, ?, ?)
    ''', (video_id, liked, notes))

    conn.commit()
    conn.close()

def get_training_data_from_database(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = '''
        SELECT vf.*, p.liked
        FROM video_features vf
        JOIN preferences p ON vf.video_id = p.video_id
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_unrated_videos_with_features_from_database(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    # Explicitly select columns to avoid duplicate column name collisions
    # (both videos and video_features have category_id)
    query = '''
        SELECT v.id, v.title, v.channel_name, v.view_count, v.duration,
               vf.title_length, vf.description_length, vf.view_like_ratio,
               vf.engagement_score, vf.title_sentiment, vf.has_tutorial_keywords,
               vf.has_time_constraint, vf.has_beginner_keywords, vf.has_ai_keywords,
               vf.has_challenge_keywords, vf.duration_seconds, vf.video_age_days,
               vf.tag_count, vf.category_id
        FROM videos v
        JOIN video_features vf ON v.id = vf.video_id
        LEFT JOIN preferences p ON v.id = p.video_id
        WHERE p.video_id IS NULL
        ORDER BY v.view_count DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_rated_count_from_database(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM preferences")
    count = cursor.fetchone()[0]
    conn.close()
    return count