import requests
import json
from typing import List, Dict

def get_video_details_from_youtube(api_key: str, video_ids: List[str]) -> List[Dict]:
    if not video_ids:
        return []
    details_url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        'key': api_key,
        'id': ','.join(video_ids),
        'part': 'snippet,statistics,contentDetails'
    }
    try:
        response = requests.get(details_url, params=params)
        data = response.json()
        videos = []
        for item in data.get('items', []):
            video = parse_youtube_video_response(item)
            videos.append(video)
        return videos
    except Exception as e:
        print(f"Error getting video details: {e}")
        return []

def get_single_video_details(api_key: str, video_id: str) -> Dict:
    results = get_video_details_from_youtube(api_key, [video_id])
    return results[0] if results else None

def parse_youtube_video_response(item: Dict) -> Dict:
    snippet = item['snippet']
    statistics = item['statistics']
    thumbnails = snippet['thumbnails']
    thumb = thumbnails.get('high', thumbnails.get('medium', thumbnails.get('default', {})))
    return {
        'id': item['id'],
        'title': snippet['title'],
        'description': snippet['description'],
        'view_count': int(statistics.get('viewCount', 0)),
        'like_count': int(statistics.get('likeCount', 0)),
        'comment_count': int(statistics.get('commentCount', 0)),
        'duration': item['contentDetails']['duration'],
        'published_at': snippet['publishedAt'],
        'channel_name': snippet['channelTitle'],
        'thumbnail_url': thumb.get('url', ''),
        'tags': json.dumps(snippet.get('tags', [])),
        'category_id': int(snippet.get('categoryId', 0)),
        'url': f"https://www.youtube.com/watch?v={item['id']}"
    }
