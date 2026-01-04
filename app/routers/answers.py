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
    infer_region_from_channel,
    get_video_thumbnail
)
from app.services.llm_service import match_question_with_llm, get_related_question, get_playlist_id, find_related_questions

router = APIRouter()

class AnswerResponse(BaseModel):
    videoLink: str
    time: str
    speakers: str
    date: str
    region: Optional[str] = None
    score: Optional[str] = None
    answerViewPoint: Optional[str] = None
    thumbnail: Optional[str] = None
    questionTitle: Optional[str] = None
    playlistId: Optional[str] = None

class AnswersResponseV1(BaseModel):
    answers: List[AnswerResponse]
    relatedQuestion: Optional[str] = None
    relatedQuestions: Optional[List[str]] = None  # For fallback when no answers found
    youtubeSearchResults: Optional[List[AnswerResponse]] = None  # For YouTube search fallback
    searchStatus: Optional[str] = None  # "qa_match", "related_questions", "youtube_search", "no_results"

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

@router.get("/answers/v1", response_model=AnswersResponseV1)
async def get_answers_v1(
    question: str = Query(..., description="User's question"),
    count: Optional[int] = Query(3, ge=1, le=10, description="Number of matches to return"),
    include_related: Optional[bool] = Query(False, description="Include related question suggestion (adds latency)")
):
    """
    Get answers from Q&A videos using LLM matching (Version 1).
    
    Matches user's question to existing questions in Q&A videos and returns
    video segments with timestamps. Only returns highly relevant matches.
    
    **Version 1**: Uses LLM to match questions from Q&A video database
    """
    try:
        # Step 1: Match question using LLM (gets more candidates, filters to top N)
        matches = match_question_with_llm(question, top_n=count)
        
        if matches:
            # Format response to match AnswerResponse model
            results = []
            matched_question_texts = []
            
            for match in matches:
                # Extract base video URL and video ID
                url = match['url']
                base_url = url.split('&t=')[0] if '&t=' in url else url
                video_id = base_url.split('watch?v=')[1] if 'watch?v=' in base_url else None
                
                # Parse timestamp
                timestamp = match.get('timestamp', '00:00:00')
                
                # Get thumbnail (sequential - YouTube API is usually fast)
                thumbnail = None
                playlist_id = None
                if video_id:
                    thumbnail = get_video_thumbnail(video_id)
                    playlist_id = get_playlist_id(video_id)
                
                # Get question text
                question_text = match.get('question_text') or match.get('question', '')
                matched_question_texts.append(question_text)
                
                result = {
                    "videoLink": base_url,
                    "time": timestamp,
                    "speakers": "Sarvapriyananda",  # Hardcoded for Version 1
                    "date": "2024-01-01",  # Placeholder - not in simplified JSON
                    "region": None,
                    "score": str(match.get('match_rank', '')),
                    "answerViewPoint": None,
                    "thumbnail": thumbnail,
                    "questionTitle": question_text,
                    "playlistId": playlist_id
                }
                results.append(result)
            
            # Get related question only if requested (adds an extra LLM call)
            related_question = None
            if include_related:
                related_question = get_related_question(question, matched_question_texts)
            
            return {
                "answers": results,
                "relatedQuestion": related_question,
                "relatedQuestions": None,
                "youtubeSearchResults": None,
                "searchStatus": "qa_match"
            }
        
        # Step 2: No Q&A matches found - try related questions
        related_questions = find_related_questions(question, num_questions=3)
        
        # Test if related questions return results
        if related_questions:
            # Try matching the first related question to see if it has results
            test_match = match_question_with_llm(related_questions[0], top_n=1)
            if test_match:
                # Related questions have results, return them
                return {
                    "answers": [],
                    "relatedQuestion": None,
                    "relatedQuestions": related_questions[:3],  # Return 2-3
                    "youtubeSearchResults": None,
                    "searchStatus": "related_questions"
                }
        
        # Step 3: Related questions also return 0 - fallback to YouTube search
        # Search YouTube for question + "Sarvapriyananda"
        # Note: We'll search without channel filter for now, can add channel_id later if needed
        youtube_query = f"{question} Sarvapriyananda"
        youtube_videos = search_videos(query=youtube_query, max_results=min(count, 5))
        
        if youtube_videos:
            youtube_results = []
            for video in youtube_videos:
                video_id = video.get('videoId')
                thumbnail_url = video.get('thumbnail', '')
                
                # Try to extract timestamp from description
                timestamp = extract_timestamp_from_description(
                    video.get('description', ''),
                    video.get('title', '')
                ) or "00:00:00"
                
                # Get playlist ID if available
                playlist_id = get_playlist_id(video_id) if video_id else None
                
                # Get better thumbnail
                if video_id:
                    better_thumbnail = get_video_thumbnail(video_id)
                    if better_thumbnail:
                        thumbnail_url = better_thumbnail
                
                result = {
                    "videoLink": format_video_link(video_id) if video_id else "",
                    "time": timestamp,
                    "speakers": video.get('channelTitle', 'Sarvapriyananda'),
                    "date": datetime.fromisoformat(
                        video.get('publishedAt', '').replace('Z', '+00:00')
                    ).strftime('%Y-%m-%d') if video.get('publishedAt') else "2024-01-01",
                    "region": None,
                    "score": None,
                    "answerViewPoint": None,
                    "thumbnail": thumbnail_url,
                    "questionTitle": video.get('title', ''),
                    "playlistId": playlist_id
                }
                youtube_results.append(result)
            
            return {
                "answers": [],
                "relatedQuestion": None,
                "relatedQuestions": None,
                "youtubeSearchResults": youtube_results,
                "searchStatus": "youtube_search"
            }
        
        # Step 4: No results found anywhere
        return {
            "answers": [],
            "relatedQuestion": None,
            "relatedQuestions": None,
            "youtubeSearchResults": None,
            "searchStatus": "no_results"
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error matching question: {str(e)}")

