from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
from app.services.youtube_service import (
    search_videos, 
    format_video_link, 
    parse_date_range,
    extract_timestamp_from_description,
    get_channel_details,
    infer_region_from_channel
)

router = APIRouter()

class AnswerResponse(BaseModel):
    videoLink: str
    time: str
    speakers: str
    date: str
    region: Optional[str] = None
    score: Optional[str] = None
    answerViewPoint: Optional[str] = None

@router.get("/answers", response_model=List[AnswerResponse])
async def get_answers(
    topic: str = Query(..., description="Topic of the question"),
    author: Optional[str] = Query(None, description="Filter by specific expert/author"),
    dateRange: Optional[str] = Query(None, description="Date range for videos (e.g., '2024-01-01,2024-12-31')"),
    count: Optional[int] = Query(10, ge=1, le=50, description="Number of results to return")
):
    """
    Get answers from YouTube videos by experts on a specific topic.
    
    This endpoint will search YouTube for videos matching the topic and expert criteria,
    and return video segments with timestamps.
    
    **Version 0**: Uses YouTube Search API
    """
    try:
        # Build search query (combine topic and author if provided)
        query = topic
        if author:
            query = f"{author} {topic}"
        
        # Parse date range
        published_after, published_before = parse_date_range(dateRange)
        
        # Search YouTube
        videos = search_videos(
            query=query,
            max_results=count,
            published_after=published_after,
            published_before=published_before
        )
        
        # Format response
        results = []
        # Cache channel details to avoid multiple API calls for same channel
        channel_cache = {}
        
        for video in videos:
            # Parse published date
            published_date = datetime.fromisoformat(
                video['publishedAt'].replace('Z', '+00:00')
            ).strftime('%Y-%m-%d')
            
            # Extract timestamp from description
            timestamp = extract_timestamp_from_description(
                video.get('description', ''),
                video.get('title', '')
            ) or "00:00:00"
            
            # Get region information
            region = None
            channel_id = video.get('channelId')
            if channel_id:
                # Check cache first
                if channel_id not in channel_cache:
                    channel_cache[channel_id] = get_channel_details(channel_id)
                
                channel_details = channel_cache[channel_id]
                region = infer_region_from_channel(
                    video.get('channelTitle', ''),
                    channel_details
                )
            
            result = {
                "videoLink": format_video_link(video['videoId']),
                "time": timestamp,
                "speakers": video['channelTitle'],
                "date": published_date,
                "region": region,
                "score": None,  # Version 0: Not calculated yet
                "answerViewPoint": None  # Version 0: Not determined yet
            }
            results.append(result)
        
        return results
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching videos: {str(e)}")

