import re
from typing import List, Dict

def remove_duplicate_videos(videos: List[Dict]) -> List[Dict]:
    seen_ids = set()
    unique_videos = []

    for video in videos:
        if video['id'] not in seen_ids:
            seen_ids.add(video['id'])
            unique_videos.append(video)

    return unique_videos


def parse_iso_duration_to_seconds(iso_duration: str) -> int:
    """Parse ISO 8601 duration (e.g. PT1M30S, PT2H5M) to total seconds."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def filter_out_shorts(videos: List[Dict], min_duration_seconds: int = 60) -> List[Dict]:
    """Remove videos shorter than the minimum duration (default 1 minute)."""
    return [
        v for v in videos
        if parse_iso_duration_to_seconds(v.get('duration', 'PT0S')) >= min_duration_seconds
    ]