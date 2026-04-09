import os
import logging
from flask import Flask, jsonify, render_template, request, redirect
from flask_cors import CORS
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from src.database.manager import setup_database_tables
from src.database.preference_operations import get_training_data_from_database, get_unrated_videos_with_features_from_database, get_rated_count_from_database, save_video_rating_to_database
from src.database.video_operations import get_unrated_videos_from_database
from src.ml.model_training import create_recommendation_model, train_model_on_user_preferences
from src.ml.predictions import predict_video_preferences_with_model

load_dotenv()

app = Flask(__name__)
CORS(app)

class DashboardAPI:
    def __init__(self):
        self.db_path = "video_inspiration.db"
        self.model = None
        self.model_trained = False
        setup_database_tables(self.db_path)
        self._initialize_model()

    def _initialize_model(self):
        rated_count = get_rated_count_from_database(self.db_path)
        if rated_count >= 10:
            self.model = create_recommendation_model()
            training_data = get_training_data_from_database(self.db_path)
            success = train_model_on_user_preferences(self.model, training_data)
            if success:
                self.model_trained = True

    def _score_videos(self, videos):
        """Score a list of videos using the model. Returns videos with 'like_probability' set."""
        if self.model_trained and self.model is not None and videos:
            import sqlite3
            import pandas as pd

            video_ids = [v['id'] for v in videos]
            placeholders = ','.join('?' for _ in video_ids)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT v.id, v.title, v.channel_name, v.view_count, v.duration,
                       vf.title_length, vf.description_length, vf.view_like_ratio,
                       vf.engagement_score, vf.title_sentiment, vf.has_tutorial_keywords,
                       vf.has_time_constraint, vf.has_beginner_keywords, vf.has_ai_keywords,
                       vf.has_challenge_keywords, vf.duration_seconds, vf.video_age_days,
                       vf.tag_count, vf.category_id
                FROM video_features vf
                JOIN videos v ON v.id = vf.video_id
                WHERE v.id IN ({placeholders})
            ''', video_ids)
            rows = cursor.fetchall()
            conn.close()

            scored_map = {}
            if rows:
                cols = ['id', 'title', 'channel_name', 'view_count', 'duration',
                        'title_length', 'description_length', 'view_like_ratio',
                        'engagement_score', 'title_sentiment', 'has_tutorial_keywords',
                        'has_time_constraint', 'has_beginner_keywords', 'has_ai_keywords',
                        'has_challenge_keywords', 'duration_seconds', 'video_age_days',
                        'tag_count', 'category_id']
                df = pd.DataFrame(rows, columns=cols)
                scored = predict_video_preferences_with_model(self.model, df)
                scored_map = {v['id']: v['like_probability'] for v in scored}

            for v in videos:
                v['like_probability'] = scored_map.get(v['id'], 0.5)
        else:
            for v in videos:
                v['like_probability'] = 0.5

    def get_recommendations(self):
        """Return ALL videos ranked by AI confidence, including rated ones."""
        import sqlite3
        from src.youtube.utils import filter_out_shorts, filter_non_english

        # Fetch all videos with their rating status
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT v.id, v.title, v.channel_name, v.view_count, v.duration,
                   p.liked as already_rated
            FROM videos v
            LEFT JOIN preferences p ON v.id = p.video_id
            ORDER BY v.created_at DESC
        ''')
        rows = cursor.fetchall()
        conn.close()

        videos = []
        for row in rows:
            videos.append({
                'id': row['id'], 'title': row['title'],
                'channel_name': row['channel_name'],
                'view_count': row['view_count'],
                'url': f"https://www.youtube.com/watch?v={row['id']}",
                'duration': row['duration'],
                'already_rated': bool(row['already_rated']),
                'liked': bool(row['already_rated']) and row['already_rated'],
            })

        # Filter
        videos = filter_out_shorts(videos)
        videos = filter_non_english(videos)

        # Score using real feature values (same as New tab)
        self._score_videos(videos)

        # Sort by confidence (highest first), rated videos slightly deprioritized
        for v in videos:
            if v['already_rated']:
                v['like_probability'] *= 0.7  # push rated ones down a bit

        videos.sort(key=lambda x: x['like_probability'], reverse=True)
        return videos[:48]

    def get_new_videos(self):
        """Return only unrated videos, sorted by AI score (highest first)."""
        import sqlite3
        import pandas as pd
        from src.youtube.utils import filter_out_shorts, filter_non_english

        if not self.model_trained or self.model is None:
            videos = get_unrated_videos_from_database(200, self.db_path)
            videos = filter_out_shorts(videos)
            videos = filter_non_english(videos)
            for v in videos:
                v['like_probability'] = 0.5
            return videos[:48]

        # Fetch unrated videos as a DataFrame with real features
        video_features = get_unrated_videos_with_features_from_database(self.db_path)

        if video_features.empty:
            return []

        # Filter to list of dicts
        videos = filter_out_shorts(video_features.to_dict('records'))
        videos = filter_non_english(videos)

        if not videos:
            return []

        # Score the filtered videos using the model
        scored_df = video_features
        # Filter the DataFrame to only include videos that passed filters
        video_id_set = set(v['id'] for v in videos)
        scored_df = scored_df[scored_df['id'].isin(video_id_set)]

        if scored_df.empty:
            for v in videos:
                v['like_probability'] = 0.5
            return videos[:48]

        scored = predict_video_preferences_with_model(self.model, scored_df)
        scored_map = {v['id']: v['like_probability'] for v in scored}
        for v in videos:
            v['like_probability'] = scored_map.get(v['id'], 0.5)

        videos.sort(key=lambda x: x.get('like_probability', 0.5), reverse=True)
        return videos[:48]

dashboard_api = DashboardAPI()

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/watch')
def watch_video():
    video_id = request.args.get('v', '')
    invidious_base = os.getenv('INVIDIOUS_BASE_URL', 'https://www.youtube.com')
    return redirect(f"{invidious_base}/watch?v={video_id}")

@app.route('/api/recommendations')
def get_recommendations():
    try:
        recommendations = dashboard_api.get_recommendations()
        formatted = []
        for video in recommendations:
            formatted.append({
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name'],
                'view_count': video['view_count'],
                'url': video['url'],
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'confidence': round(video.get('like_probability', 0.5) * 100),
                'views_formatted': format_view_count(video['view_count']),
                'duration_formatted': format_duration(video.get('duration', '')),
                'already_rated': video.get('already_rated', False),
                'liked': video.get('liked', False),
            })
        return jsonify({
            'success': True,
            'videos': formatted,
            'model_trained': dashboard_api.model_trained,
            'total_ratings': get_rated_count_from_database(dashboard_api.db_path)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/recently_added')
def get_recently_added():
    try:
        videos = dashboard_api.get_new_videos()
        logger.info(f"get_recently_added: returning {len(videos)} videos")
        formatted = []
        for video in videos:
            formatted.append({
                'id': video['id'], 'title': video['title'], 'channel_name': video['channel_name'],
                'view_count': video['view_count'], 'url': video.get('url', f"https://www.youtube.com/watch?v={video['id']}"),
                'thumbnail': f"https://img.youtube.com/vi/{video['id']}/hqdefault.jpg",
                'confidence': round(video.get('like_probability', 0.5) * 100),
                'views_formatted': format_view_count(video['view_count']),
                'duration_formatted': format_duration(video.get('duration', '')),
                'already_rated': False,
                'liked': False,
            })
        return jsonify({'success': True, 'videos': formatted, 'total_ratings': get_rated_count_from_database(dashboard_api.db_path)})
    except Exception as e:
        logger.exception(f"Error in get_recently_added: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rate', methods=['POST'])
def rate_video():
    try:
        data = request.json
        video_id = data.get('video_id')
        liked = data.get('liked')
        if not video_id or liked is None:
            return jsonify({'success': False, 'error': 'Missing video_id or liked parameter'}), 400
        save_video_rating_to_database(video_id, liked, "", dashboard_api.db_path)
        model_retrained = False
        rated_count = get_rated_count_from_database(dashboard_api.db_path)
        if rated_count >= 10:
            if dashboard_api.model is None:
                dashboard_api.model = create_recommendation_model()
            training_data = get_training_data_from_database(dashboard_api.db_path)
            success = train_model_on_user_preferences(dashboard_api.model, training_data)
            if success:
                dashboard_api.model_trained = True
                model_retrained = True
        return jsonify({
            'success': True,
            'message': 'Rating saved',
            'model_retrained': model_retrained,
            'total_ratings': rated_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fetch_more', methods=['POST'])
def fetch_more():
    try:
        from src.youtube.search import search_youtube_videos_by_query, get_coding_search_queries
        from src.youtube.details import get_video_details_from_youtube
        from src.youtube.utils import remove_duplicate_videos, filter_out_shorts, filter_non_english
        from src.database.video_operations import save_videos_to_database, save_video_features_to_database
        from src.ml.feature_extraction import extract_all_features_from_video

        api_key = os.getenv('YOUTUBE_API_KEY')
        db_path = dashboard_api.db_path

        if not api_key:
            logger.error("YOUTUBE_API_KEY is not set")
            return jsonify({'success': False, 'error': 'YOUTUBE_API_KEY not set in environment'}), 400

        logger.info("Starting fetch_more...")

        queries = get_coding_search_queries()
        logger.info(f"Search queries ({len(queries)}): {queries}")

        all_videos = []
        per_query_counts = {}
        for query in queries:
            try:
                ids = search_youtube_videos_by_query(api_key, query, 20)
                per_query_counts[query] = len(ids)
                logger.info(f"  Query '{query}': {len(ids)} video IDs returned")
                if ids:
                    videos = get_video_details_from_youtube(api_key, ids)
                    logger.info(f"  Query '{query}': {len(videos)} video details fetched")
                    all_videos.extend(videos)
                else:
                    logger.warning(f"  Query '{query}': No IDs returned — may be API quota or no results")
            except Exception as e:
                logger.error(f"  Query '{query}' failed: {e}")

        total_found = len(all_videos)
        logger.info(f"Total raw videos collected: {total_found}")

        if total_found == 0:
            return jsonify({'success': True, 'fetched': 0, 'duplicates': 0, 'detail': 'No videos found from any query — check API key quota or results'})

        unique = remove_duplicate_videos(all_videos)
        logger.info(f"After dedup: {len(unique)} (removed {total_found - len(unique)} duplicates)")

        unique = filter_out_shorts(unique)
        logger.info(f"After filtering shorts: {len(unique)}")

        unique = filter_non_english(unique)
        logger.info(f"After filtering non-English: {len(unique)}")

        save_videos_to_database(unique, db_path)
        logger.info(f"Saved {len(unique)} videos to database")

        for v in unique:
            features = extract_all_features_from_video(v)
            save_video_features_to_database(v['id'], features, db_path)
        logger.info(f"Extracted features for {len(unique)} videos")

        return jsonify({'success': True, 'fetched': len(unique), 'duplicates': total_found - len(unique)})
    except Exception as e:
        logger.exception(f"Unhandled error in fetch_more: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search_terms', methods=['GET'])
def get_search_terms():
    from src.youtube.search import get_coding_search_queries
    return jsonify({'success': True, 'terms': get_coding_search_queries()})

@app.route('/api/search_terms', methods=['POST'])
def update_search_terms():
    try:
        data = request.json
        terms = data.get('terms', [])
        terms_repr = ',\n        '.join([f'"{t}"' for t in terms])
        new_content = f'''import requests
from typing import List, Dict

def search_youtube_videos_by_query(api_key: str, query: str, max_results: int) -> List[Dict]:
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {{
        'key': api_key,
        'q': query,
        'part': 'snippet',
        'type': 'video',
        'order': 'viewCount',
        'maxResults': max_results,
        'videoCategoryId': '28',
        'publishedAfter': '2020-01-01T00:00:00Z'
    }}
    try:
        response = requests.get(search_url, params=params)
        data = response.json()
        if 'items' not in data:
            return []
        video_ids = [item['id']['videoId'] for item in data['items']]
        return video_ids
    except Exception as e:
        print(f"Error searching videos: {{e}}")
        return []

def get_coding_search_queries() -> List[str]:
    return [
        {terms_repr},
    ]
'''
        with open('src/youtube/search.py', 'w') as f:
            f.write(new_content)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def format_view_count(count):
    if count >= 1000000:
        return f"{count/1000000:.1f}M views"
    elif count >= 1000:
        return f"{count/1000:.1f}K views"
    else:
        return f"{count} views"

def format_duration(iso_duration):
    """Convert ISO 8601 duration (PT1H2M30S) to readable format (1:02:30)."""
    if not iso_duration:
        return ''
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return ''
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)

@app.route('/api/add_video', methods=['POST'])
def add_video():
    try:
        from src.youtube.details import get_single_video_details
        from src.database.video_operations import save_videos_to_database, save_video_features_to_database
        from src.ml.feature_extraction import extract_all_features_from_video
        import re

        data = request.json
        url = data.get('url', '').strip()

        # Extract video ID from URL
        match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
        if not match:
            return jsonify({'success': False, 'error': 'Could not find a valid YouTube video ID in that URL'}), 400

        video_id = match.group(1)
        api_key = os.getenv('YOUTUBE_API_KEY')
        video = get_single_video_details(api_key, video_id)

        if not video:
            return jsonify({'success': False, 'error': 'Could not fetch video details — check your API key or the video ID'}), 400

        save_videos_to_database([video], dashboard_api.db_path)
        features = extract_all_features_from_video(video)
        save_video_features_to_database(video['id'], features, dashboard_api.db_path)

        return jsonify({
            'success': True,
            'video': {
                'id': video['id'],
                'title': video['title'],
                'channel_name': video['channel_name']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
