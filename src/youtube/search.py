import requests
from typing import List, Dict

def search_youtube_videos_by_query(api_key: str, query: str, max_results: int) -> List[Dict]:
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        'key': api_key,
        'q': query,
        'part': 'snippet',
        'type': 'video',
        'order': 'viewCount',
        'maxResults': max_results,
        'videoCategoryId': '28',
        'publishedAfter': '2020-01-01T00:00:00Z'
    }
    try:
        response = requests.get(search_url, params=params)
        data = response.json()
        if 'items' not in data:
            return []
        video_ids = [item['id']['videoId'] for item in data['items']]
        return video_ids
    except Exception as e:
        print(f"Error searching videos: {e}")
        return []

def get_coding_search_queries() -> List[str]:
    return [
        "nuzlocke",
        "pokemon",
        "minecraft",
        "data science",
        "fly fishing",
        "fly fishing carp",
        "Video essay",
        "Premier league",
        "Science",
        "Math",
        "Technology",
        "AI",
        "deep dive",
        "explained",
        "analysis",
        "physics",
        "speedrun",
        "chess",
        "engineering",
        "lost media",
        "history documentary",
        "philosophy",
        "economics",
        "internet history",
        "case study",
        "breakdown",
        "lecture",
        "game design",
        "cold case",
        "film analysis",
        "political science",
        "interrogation",
        "true crime",
    ]
