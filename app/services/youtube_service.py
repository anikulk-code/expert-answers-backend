from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os
from typing import List, Optional, Dict
from datetime import datetime

# Initialize YouTube API client
youtube_service = None

def get_youtube_service():
    """Initialize and return YouTube API service client"""
    global youtube_service
    if youtube_service is None:
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY not found in environment variables")
        youtube_service = build('youtube', 'v3', developerKey=api_key)
    return youtube_service

def search_videos(
    query: str,
    channel_id: Optional[str] = None,
    max_results: int = 10,
    published_after: Optional[str] = None,
    published_before: Optional[str] = None
) -> List[Dict]:
    """
    Search for YouTube videos
    
    Args:
        query: Search query string
        channel_id: Optional channel ID to filter by
        max_results: Maximum number of results (default: 10, max: 50)
        published_after: ISO 8601 date string (e.g., '2024-01-01T00:00:00Z')
        published_before: ISO 8601 date string
    
    Returns:
        List of video dictionaries with id, title, description, publishedAt, channelTitle
    """
    try:
        service = get_youtube_service()
        
        # Build search request
        request_params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': min(max_results, 50),
            'order': 'relevance'
        }
        
        if channel_id:
            request_params['channelId'] = channel_id
        
        if published_after:
            request_params['publishedAfter'] = published_after
        
        if published_before:
            request_params['publishedBefore'] = published_before
        
        # Execute search
        request = service.search().list(**request_params)
        response = request.execute()
        
        # Extract video information
        videos = []
        for item in response.get('items', []):
            video_data = {
                'videoId': item['id']['videoId'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'publishedAt': item['snippet']['publishedAt'],
                'channelTitle': item['snippet']['channelTitle'],
                'channelId': item['snippet']['channelId'],
                'thumbnail': item['snippet']['thumbnails'].get('default', {}).get('url', '')
            }
            videos.append(video_data)
        
        return videos
    
    except HttpError as e:
        print(f"YouTube API error: {e}")
        raise Exception(f"YouTube API error: {str(e)}")
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        raise

def format_video_link(video_id: str) -> str:
    """Format video ID into YouTube URL"""
    return f"https://www.youtube.com/watch?v={video_id}"

def parse_date_range(date_range: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Parse date range string into published_after and published_before
    
    Args:
        date_range: String in format "YYYY-MM-DD,YYYY-MM-DD" or None
    
    Returns:
        Tuple of (published_after, published_before) in ISO 8601 format
    """
    if not date_range:
        return None, None
    
    try:
        parts = date_range.split(',')
        if len(parts) == 2:
            start_date = parts[0].strip()
            end_date = parts[1].strip()
            # Convert to ISO 8601 format
            published_after = f"{start_date}T00:00:00Z" if start_date else None
            published_before = f"{end_date}T23:59:59Z" if end_date else None
            return published_after, published_before
    except Exception as e:
        print(f"Error parsing date range: {e}")
    
    return None, None

def extract_timestamp_from_description(description: str, title: str = "") -> Optional[str]:
    """
    Extract timestamp from video description or title.
    Looks for patterns like "5:30", "10:15", "1:23:45", "00:05:30", etc.
    
    Args:
        description: Video description text
        title: Video title (optional, also searched)
    
    Returns:
        Timestamp string in HH:MM:SS format, or None if not found
    """
    import re
    
    # Combine title and description for searching
    text = f"{title} {description}".lower()
    
    # Pattern 1: HH:MM:SS format (e.g., "1:23:45", "00:05:30")
    pattern1 = r'\b(\d{1,2}):(\d{2}):(\d{2})\b'
    matches = re.findall(pattern1, text)
    if matches:
        # Take the first match
        h, m, s = matches[0]
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    
    # Pattern 2: MM:SS format (e.g., "5:30", "10:15")
    pattern2 = r'\b(\d{1,2}):(\d{2})\b'
    matches = re.findall(pattern2, text)
    if matches:
        # Filter out likely false positives (like dates, URLs)
        for match in matches:
            m, s = match
            # Skip if it looks like a date (month:day) or URL
            if int(m) <= 12 and 'http' not in text[max(0, text.find(f"{m}:{s}")-10):text.find(f"{m}:{s}")+10]:
                # Check if it's a reasonable timestamp (minutes < 60)
                if int(m) < 60:
                    return f"00:{int(m):02d}:{int(s):02d}"
    
    # Pattern 3: Look for "at X:XX" or "timestamp X:XX" patterns
    pattern3 = r'(?:at|timestamp|time|start|begins?)\s*:?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?'
    matches = re.findall(pattern3, text)
    if matches:
        match = matches[0]
        if len(match) == 3 and match[2]:  # Has seconds
            h, m, s = match
            return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
        elif len(match) >= 2:  # MM:SS format
            m, s = match[0], match[1]
            if int(m) < 60:
                return f"00:{int(m):02d}:{int(s):02d}"
    
    return None

def get_channel_details(channel_id: str) -> Optional[Dict]:
    """
    Get channel details including location/region information
    
    Args:
        channel_id: YouTube channel ID
    
    Returns:
        Dictionary with channel details including location, or None if error
    """
    try:
        service = get_youtube_service()
        request = service.channels().list(
            part='snippet,contentDetails',
            id=channel_id
        )
        response = request.execute()
        
        if response.get('items'):
            channel = response['items'][0]
            snippet = channel.get('snippet', {})
            return {
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'country': snippet.get('country', ''),
                'customUrl': snippet.get('customUrl', '')
            }
    except Exception as e:
        print(f"Error fetching channel details: {e}")
    
    return None

def infer_region_from_channel(channel_title: str, channel_details: Optional[Dict] = None) -> Optional[str]:
    """
    Infer region from channel information
    
    Args:
        channel_title: Channel title
        channel_details: Optional channel details dictionary
    
    Returns:
        Region string or None
    """
    # Check channel details first
    if channel_details and channel_details.get('country'):
        country_code = channel_details['country']
        # Map common country codes to readable names
        country_map = {
            'US': 'United States',
            'IN': 'India',
            'GB': 'United Kingdom',
            'CA': 'Canada',
            'AU': 'Australia',
            'DE': 'Germany',
            'FR': 'France',
            'JP': 'Japan',
            'CN': 'China'
        }
        return country_map.get(country_code, country_code)
    
    # Try to infer from channel title
    title_lower = channel_title.lower()
    region_keywords = {
        'new york': 'United States',
        'california': 'United States',
        'london': 'United Kingdom',
        'mumbai': 'India',
        'delhi': 'India',
        'bangalore': 'India',
        'sydney': 'Australia',
        'toronto': 'Canada'
    }
    
    for keyword, region in region_keywords.items():
        if keyword in title_lower:
            return region
    
    return None

