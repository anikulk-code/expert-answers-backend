from fastapi import APIRouter, HTTPException, Query, Body
from typing import Optional, List, Dict
from pydantic import BaseModel
from datetime import datetime
from app.services.youtube_service import (
    search_videos, 
    format_video_link, 
    parse_date_range,
    extract_timestamp_from_description,
    get_channel_details,
    infer_region_from_channel,
    get_video_thumbnail,
    search_sarvapriyananda_videos
)
from app.services.llm_service import match_question_with_llm, get_related_question, get_playlist_id, find_related_questions, distill_question_for_search, find_similar_questions_for_upvote, check_youtube_video_relevance, is_precanned_question

router = APIRouter()

# Import Cosmos DB service
from app.services.cosmos_service import (
    add_question_to_queue,
    upvote_question,
    find_question_by_text,
    get_questions_queue,
    find_similar_questions_in_queue
)
from app.services.search_service import search_all_methods

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

class TagSuggestion(BaseModel):
    tag: str
    count: int

class SimilarQuestionForUpvote(BaseModel):
    question: str
    upvotes: int
    inQueue: bool

class QueueInfo(BaseModel):
    questionInQueue: bool
    upvotes: int
    similarQuestions: Optional[List[SimilarQuestionForUpvote]] = None  # Similar questions for upvoting
    canPostNewQuestion: bool = True  # Whether user can post their own question

def _build_queue_info(question: str) -> QueueInfo:
    """Helper function to build QueueInfo for a question"""
    # Get similar questions using topics search + LLM filtering (returns dicts with 'question' and 'upvotes')
    similar_db_questions_data = find_similar_questions_for_upvote(question, num_questions=5)
    question_in_db = find_question_by_text(question)
    in_queue = question_in_db is not None
    # Support both "votes" and "upvotes" for backward compatibility
    upvotes = question_in_db.get("votes", question_in_db.get("upvotes", 0)) if question_in_db else 0
    similar_questions_for_upvote = []
    
    # Add similar questions from database (already have votes from Cosmos DB)
    for q_data in similar_db_questions_data:
        if isinstance(q_data, dict):
            # New format: dict with 'question' and 'upvotes'
            db_question = q_data.get('question', '')
            db_upvotes = q_data.get('upvotes', 0)
            # Check if question exists in DB to determine inQueue status
            db_question_in_db = find_question_by_text(db_question)
            similar_questions_for_upvote.append(SimilarQuestionForUpvote(
                question=db_question, 
                upvotes=db_upvotes, 
                inQueue=db_question_in_db is not None
            ))
        else:
            # Legacy format: just question text (backward compatibility)
            db_question = q_data if isinstance(q_data, str) else q_data.get('question', '')
            db_question_in_db = find_question_by_text(db_question)
            db_upvotes = db_question_in_db.get("voteUp", db_question_in_db.get("votes", db_question_in_db.get("upvotes", 0))) if db_question_in_db else 0
            similar_questions_for_upvote.append(SimilarQuestionForUpvote(
                question=db_question, 
                upvotes=db_upvotes, 
                inQueue=db_question_in_db is not None
            ))
    
    # Also add similar questions from queue
    try:
        similar_queue_questions = find_similar_questions_in_queue(question, limit=5)
        for queue_item in similar_queue_questions:
            queue_question = queue_item.get("question", "")
            queue_question_lower = queue_question.strip().lower()
            question_lower = question.strip().lower()
            # Skip if it's the same question or already in list
            if queue_question_lower != question_lower and not any(sq.question.strip().lower() == queue_question_lower for sq in similar_questions_for_upvote):
                similar_questions_for_upvote.append(SimilarQuestionForUpvote(
                    question=queue_question, 
                    upvotes=queue_item.get("voteUp", queue_item.get("votes", queue_item.get("upvotes", 0))), 
                    inQueue=True
                ))
    except Exception as e:
        print(f"Error finding similar questions in queue: {e}")
    
    # Sort by upvotes (highest first) and limit to top 5
    similar_questions_for_upvote = sorted(similar_questions_for_upvote, key=lambda x: x.upvotes, reverse=True)[:5]
    return QueueInfo(
        questionInQueue=in_queue, 
        upvotes=upvotes, 
        similarQuestions=similar_questions_for_upvote if similar_questions_for_upvote else None, 
        canPostNewQuestion=True
    )

class AnswersResponseV1(BaseModel):
    answers: List[AnswerResponse]
    relatedQuestion: Optional[str] = None
    relatedQuestions: Optional[List[str]] = None  # For fallback when no answers found
    youtubeSearchResults: Optional[List[AnswerResponse]] = None  # For YouTube search fallback
    searchStatus: Optional[str] = None  # "qa_match", "youtube_fallback", "tags_fallback", "no_results"
    searchStage: Optional[str] = None  # "searching_questions", "searching_videos", "checking_relevance", "complete"
    suggestedTags: Optional[List[TagSuggestion]] = None  # For tags fallback
    queueInfo: Optional[QueueInfo] = None  # For queue/upvote info
    userMessage: Optional[str] = None  # User-facing message explaining the result

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

# Cache for full endpoint responses (only for precanned questions)
_endpoint_response_cache = {}

@router.get("/answers/v1", response_model=AnswersResponseV1)
async def get_answers_v1(
    question: str = Query(..., description="User's question"),
    count: Optional[int] = Query(3, ge=1, le=10, description="Number of matches to return"),
    include_related: Optional[bool] = Query(False, description="Include related question suggestion (adds latency)"),
    strict: Optional[bool] = Query(False, description="Strict mode: only return results with high relevance confidence")
):
    """
    Get answers from Q&A videos using LLM matching (Version 1).
    
    Matches user's question to existing questions in Q&A videos and returns
    video segments with timestamps. Only returns highly relevant matches.
    
    **Version 1**: Uses LLM to match questions from Q&A video database
    """
    try:
        # Check cache for precanned questions (full response including thumbnails)
        if is_precanned_question(question):
            cache_key = f"{question.lower().strip()}:{count}:{include_related}"
            if cache_key in _endpoint_response_cache:
                print(f"   ✅ Returning cached full response for precanned question")
                return _endpoint_response_cache[cache_key]
        
        # Step 1: Match question using LLM (gets more candidates, filters to top N)
        # Note: In a real async implementation, we could stream progress updates
        # For now, we'll set searchStage at key points
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
            
            # Load queue info with similar questions for upvoting
            # This allows users to see related questions they can upvote, or add their own question
            # (in case the answers aren't what they're looking for)
            # Note: We load similar questions here so they're available when the queue is shown
            queue_info = _build_queue_info(question)
            
            response = {
                "answers": results,
                "relatedQuestion": related_question,
                "relatedQuestions": None,
                "youtubeSearchResults": None,
                "searchStatus": "qa_match",
                "searchStage": "complete",
                "suggestedTags": None,
                "queueInfo": queue_info,
                "userMessage": None
            }
            
            # Cache full response for precanned questions (including thumbnails)
            if is_precanned_question(question):
                cache_key = f"{question.lower().strip()}:{count}:{include_related}"
                _endpoint_response_cache[cache_key] = response
                print(f"   ✅ Cached full response for precanned question")
            
            return response
        
        # Step 2: No Q&A matches found - show tags and queue/upvote options
        from app.routers.tags import load_tagged_chapters
        
        # Get tags
        suggested_tags = None
        try:
            chapters = load_tagged_chapters()
            # Count questions per tag
            tag_counts: Dict[str, int] = {}
            for chapter in chapters:
                primary_tag = chapter.get("primary_tag", "Other")
                tag_counts[primary_tag] = tag_counts.get(primary_tag, 0) + 1
            
            # Convert to list and sort, but move "Other" to the end
            tags_list = [
                TagSuggestion(tag=tag, count=count)
                for tag, count in tag_counts.items()
            ]
            
            # Sort alphabetically, but put "Other" at the end
            def sort_key(tag_info):
                if tag_info.tag.lower() == "other":
                    return (1, tag_info.tag.lower())
                return (0, tag_info.tag.lower())
            
            sorted_tags = sorted(tags_list, key=sort_key)
            suggested_tags = sorted_tags[:5]  # Top 5 tags
        except (HTTPException, Exception) as e:
            print(f"Error loading tags: {e}")
            suggested_tags = None
        
        # Find similar questions from the database for upvoting (using topics search + LLM)
        # Returns list of dicts with 'question' and 'upvotes'
        similar_db_questions_data = find_similar_questions_for_upvote(question, num_questions=5)
        
        # Check if question is in queue and get upvotes from Cosmos DB
        question_in_db = find_question_by_text(question)
        in_queue = question_in_db is not None
        # Support both old and new schema
        upvotes = question_in_db.get("voteUp", question_in_db.get("votes", question_in_db.get("upvotes", 0))) if question_in_db else 0
        
        # Build list of similar questions for upvoting (from database + Cosmos DB queue)
        similar_questions_for_upvote = []
        
        # Add similar questions from Q&A database (already have votes from Cosmos DB)
        for q_data in similar_db_questions_data:
            if isinstance(q_data, dict):
                # New format: dict with 'question' and 'upvotes'
                db_question = q_data.get('question', '')
                db_upvotes = q_data.get('upvotes', 0)
                db_question_in_db = find_question_by_text(db_question)
                similar_questions_for_upvote.append(
                    SimilarQuestionForUpvote(
                        question=db_question,
                        upvotes=db_upvotes,
                        inQueue=db_question_in_db is not None
                    )
                )
            else:
                # Legacy format: just question text (backward compatibility)
                db_question = q_data if isinstance(q_data, str) else q_data.get('question', '')
                db_question_in_db = find_question_by_text(db_question)
                db_upvotes = db_question_in_db.get("voteUp", db_question_in_db.get("votes", db_question_in_db.get("upvotes", 0))) if db_question_in_db else 0
                similar_questions_for_upvote.append(
                    SimilarQuestionForUpvote(
                        question=db_question,
                        upvotes=db_upvotes,
                        inQueue=db_question_in_db is not None
                    )
                )
        
        # Add similar questions from Cosmos DB queue
        try:
            similar_queue_questions = find_similar_questions_in_queue(question, limit=5)
            for queue_item in similar_queue_questions:
                queue_question = queue_item.get("question", "")
                queue_question_lower = queue_question.strip().lower()
                question_lower = question.strip().lower()
                
                # Skip if it's the same question or already in list
                if queue_question_lower != question_lower and \
                   not any(sq.question.strip().lower() == queue_question_lower for sq in similar_questions_for_upvote):
                    similar_questions_for_upvote.append(
                        SimilarQuestionForUpvote(
                            question=queue_question,
                            upvotes=queue_item.get("voteUp", queue_item.get("votes", queue_item.get("upvotes", 0))),
                            inQueue=True
                        )
                    )
        except Exception as e:
            print(f"Error finding similar questions in queue: {e}")
            # Continue without queue questions if Cosmos DB is unavailable
        
        # Limit to top 5 similar questions, sorted by upvotes
        similar_questions_for_upvote = sorted(
            similar_questions_for_upvote, 
            key=lambda x: x.upvotes, 
            reverse=True
        )[:5]
        
        queue_info = QueueInfo(
            questionInQueue=in_queue,
            upvotes=upvotes,
            similarQuestions=similar_questions_for_upvote if similar_questions_for_upvote else None,
            canPostNewQuestion=True
        )
        
        return {
            "answers": [],
            "relatedQuestion": None,
            "relatedQuestions": None,
            "youtubeSearchResults": None,
            "searchStatus": "tags_fallback",
            "searchStage": "complete",
            "suggestedTags": suggested_tags,
            "queueInfo": queue_info,
            "userMessage": "We couldn't find your question in our database. You can upvote similar questions or add your question to our queue."
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error matching question: {str(e)}")

class SearchResultItem(BaseModel):
    """Individual search result item"""
    id: str
    questionText: Optional[str] = None
    domain: Optional[str] = None
    topics: Optional[List[str]] = None
    entities: Optional[List[Dict]] = None
    video_link: Optional[str] = None
    full_video_link: Optional[str] = None
    playlist_link: Optional[str] = None
    voteUp: Optional[int] = None
    score: Optional[float] = None  # Search-specific score (bm25_score, topic_entity_score, etc.)
    vector_score: Optional[float] = None  # Vector similarity score (for combined results)
    topic_entity_score: Optional[float] = None  # Topic/entity match score (for combined results)

class TopicEntitySearchResponse(BaseModel):
    """Response for topic/entity search endpoint"""
    query_topics: List[str]
    query_entities: List[Dict]
    results: List[SearchResultItem]

class SearchComparisonResponse(BaseModel):
    """Response for search comparison endpoint"""
    query: str
    vector_results: List[SearchResultItem]
    topic_entity_results: List[SearchResultItem]
    total_questions_in_db: int

class CombinedSearchResponse(BaseModel):
    """Response for combined search endpoint"""
    query: str
    results: List[SearchResultItem]
    total_questions_in_db: int

class QueueQuestionRequest(BaseModel):
    question: str
    domain: Optional[str] = None  # e.g., "philosophy", "technology", "medicine"
    video_link: Optional[str] = None
    full_video_link: Optional[str] = None
    playlist_link: Optional[str] = None
    tags: Optional[List[str]] = None  # Broader/UI-facing tags
    embedding: Optional[List[float]] = None  # Vector embedding
    embedding_model: Optional[str] = None  # e.g., "text-embedding-3-large"
    embedding_dim: Optional[int] = None  # Dimension of embedding

class UpvoteQuestionRequest(BaseModel):
    question: str

@router.get("/search/bm25", response_model=List[SearchResultItem])
async def search_bm25(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(5, ge=1, le=50, description="Number of results to return")
):
    """
    BM25 (keyword-based) search only.
    Returns results sorted by BM25 score.
    """
    try:
        from app.services.search_service import bm25_search
        results = bm25_search(query, top_n)
        
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=q.get("questionText", q.get("question", "")),
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=q.get("video_link"),
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", q.get("votes", q.get("upvotes", 0))),
                score=q.get("bm25_score")
            )
        
        return [convert_to_result_item(q) for q in results]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in BM25 search: {str(e)}")


@router.get("/search/vector", response_model=List[SearchResultItem])
async def search_vector(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(5, ge=1, le=50, description="Number of results to return")
):
    """
    Vector (semantic) search only.
    Returns results sorted by vector similarity.
    """
    try:
        print(f"🔍 /api/search/vector endpoint called with query: '{query}', top_n: {top_n}")
        from app.services.search_service import vector_search
        results = vector_search(query, top_n)
        print(f"✅ /api/search/vector returning {len(results)} results")
        
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=q.get("questionText", q.get("question", "")),
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=q.get("video_link"),
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", q.get("votes", q.get("upvotes", 0))),
                score=q.get("vector_score")
            )
        
        return [convert_to_result_item(q) for q in results]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in vector search: {str(e)}")


@router.get("/search/topic-entity", response_model=TopicEntitySearchResponse)
async def search_topic_entity(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(50, ge=1, le=100, description="Number of results to return")
):
    """
    Topic/Entity search only.
    Returns results sorted by topic and entity match score, plus extracted query topics/entities.
    """
    try:
        from app.services.search_service import topic_entity_search
        from app.services.question_processor import extract_topics_and_entities
        
        # Extract topics and entities from the query
        query_analysis = extract_topics_and_entities(query)
        
        results = topic_entity_search(query, top_n)
        
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=q.get("questionText", q.get("question", "")),
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=q.get("video_link"),
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", q.get("votes", q.get("upvotes", 0))),
                score=q.get("topic_entity_score")
            )
        
        return {
            "query_topics": query_analysis.get("topics", []),
            "query_entities": query_analysis.get("entities", []),
            "results": [convert_to_result_item(q) for q in results]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in topic/entity search: {str(e)}")


@router.get("/search/llm-filtered", response_model=CombinedSearchResponse)
async def llm_filtered_search(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(5, ge=1, le=20, description="Number of results to return")
):
    """
    LLM-filtered search using vector + topics search, then LLM filtering.
    This is what the homepage uses.
    """
    print(f"🔍 /api/search/llm-filtered endpoint called with query: '{query}', top_n: {top_n}")
    try:
        from app.services.llm_service import match_question_with_llm
        
        print(f"🔍 LLM-filtered search called with query: '{query}', top_n: {top_n}")
        # Use the same LLM matching function as the homepage
        llm_results = match_question_with_llm(query, top_n=top_n)
        print(f"🔍 LLM-filtered search returned {len(llm_results)} results")
        
        if llm_results:
            print(f"   First result keys: {list(llm_results[0].keys())}")
            print(f"   First result sample: id={llm_results[0].get('id', 'N/A')[:20]}, question={llm_results[0].get('question', llm_results[0].get('questionText', 'N/A'))[:50]}, url={llm_results[0].get('url', llm_results[0].get('video_link', 'N/A'))[:50]}")
        else:
            print(f"   ⚠️  No results returned from LLM filtering")
        
        # Get total count
        from app.services.cosmos_service import get_cosmos_container
        container = get_cosmos_container()
        count_query = "SELECT VALUE COUNT(1) FROM c"
        try:
            total_count = list(container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))[0]
        except Exception as e:
            print(f"Warning: Could not get total count: {e}")
            total_count = 0
        
        # Convert to SearchResultItem format
        # Note: match_question_with_llm returns items with 'url' and 'question' fields,
        # but we need to convert them to 'video_link' and 'questionText' for consistency
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            # LLM returns 'url' but we need 'video_link'
            video_link = q.get("video_link") or q.get("url", "")
            # LLM returns 'question' but we need 'questionText'
            question_text = q.get("questionText") or q.get("question") or q.get("question_text", "")
            
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=question_text,
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=video_link,
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", 0),
                score=None  # LLM doesn't provide scores
            )
        
        return CombinedSearchResponse(
            query=query,
            results=[convert_to_result_item(q) for q in llm_results],
            total_questions_in_db=total_count
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in LLM-filtered search: {str(e)}")


@router.get("/search/combined", response_model=CombinedSearchResponse)
async def combined_search(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(5, ge=1, le=100, description="Number of results to return")
):
    """
    Combined search using both vector and topics search.
    Returns merged and deduplicated results, sorted by highest score.
    """
    try:
        from app.services.search_service import vector_search, topic_entity_search
        from app.services.cosmos_service import get_cosmos_container
        
        # Get results from both methods
        vector_results = vector_search(query, top_n=top_n)
        topic_results = topic_entity_search(query, top_n=top_n)
        
        print(f"🔍 Combined search: vector_results={len(vector_results)}, topic_results={len(topic_results)}")
        
        # Get total count
        container = get_cosmos_container()
        count_query = "SELECT VALUE COUNT(1) FROM c"
        try:
            total_count = list(container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))[0]
        except Exception as e:
            print(f"Warning: Could not get total count: {e}")
            total_count = 0
        
        # Combine and deduplicate by ID
        results_dict = {}
        vector_ids = set()
        topic_ids = set()
        
        # First, find max topic score for normalization (topic scores can be 0-4+)
        max_topic_score = 0.0
        for item in topic_results:
            topic_score = item.get("topic_entity_score", 0.0) or 0.0
            if topic_score > max_topic_score:
                max_topic_score = topic_score
        
        # If no topic scores, use a default max (4.0 is typical max: 2.0 per topic * 2x bonus)
        if max_topic_score == 0.0:
            max_topic_score = 4.0
        else:
            # Add some headroom for potential higher scores
            max_topic_score = max(max_topic_score * 1.2, 4.0)
        
        print(f"🔍 Normalizing topic scores: max_topic_score={max_topic_score:.2f}")
        
        # Add vector results (vector scores are already 0-1, no normalization needed)
        for item in vector_results:
            item_id = item.get("id")
            if item_id:
                vector_ids.add(item_id)
                vector_score = item.get("vector_score")
                # Vector scores are already normalized (0-1)
                normalized_vector = vector_score if vector_score is not None else 0.0
                results_dict[item_id] = {
                    "id": item_id,
                    "questionText": item.get("questionText", item.get("question", "")),
                    "domain": item.get("domain"),
                    "topics": item.get("topics", []),
                    "entities": item.get("entities", []),
                    "video_link": item.get("video_link"),
                    "full_video_link": item.get("full_video_link"),
                    "playlist_link": item.get("playlist_link"),
                    "voteUp": item.get("voteUp", item.get("votes", item.get("upvotes", 0))),
                    "vector_score": vector_score,  # Keep original for display
                    "topic_entity_score": None,
                    "combined_score": normalized_vector  # Use normalized for ranking
                }
        
        # Add topic results (normalize topic scores to 0-1)
        items_in_both = 0
        for item in topic_results:
            item_id = item.get("id")
            if item_id:
                topic_ids.add(item_id)
                topic_score = item.get("topic_entity_score", 0.0) or 0.0
                # Normalize topic score to 0-1 range
                normalized_topic = topic_score / max_topic_score if max_topic_score > 0 else 0.0
                normalized_topic = min(normalized_topic, 1.0)  # Cap at 1.0
                
                if item_id in results_dict:
                    # Merge: add topic score to existing (item appears in both lists)
                    items_in_both += 1
                    results_dict[item_id]["topic_entity_score"] = topic_score  # Keep original for display
                    # Combined score: use max of normalized scores, with bonus for appearing in both
                    normalized_vector = results_dict[item_id].get("vector_score", 0.0) or 0.0
                    # Give 10% bonus for appearing in both lists
                    combined_normalized = max(normalized_vector, normalized_topic) * 1.1
                    results_dict[item_id]["combined_score"] = min(combined_normalized, 1.0)  # Cap at 1.0
                else:
                    # New item from topics search only
                    results_dict[item_id] = {
                        "id": item_id,
                        "questionText": item.get("questionText", item.get("question", "")),
                        "domain": item.get("domain"),
                        "topics": item.get("topics", []),
                        "entities": item.get("entities", []),
                        "video_link": item.get("video_link"),
                        "full_video_link": item.get("full_video_link"),
                        "playlist_link": item.get("playlist_link"),
                        "voteUp": item.get("voteUp", item.get("votes", item.get("upvotes", 0))),
                        "vector_score": None,
                        "topic_entity_score": topic_score,  # Keep original for display
                        "combined_score": normalized_topic  # Use normalized for ranking
                    }
        
        print(f"🔍 Combined search: {len(vector_ids)} vector IDs, {len(topic_ids)} topic IDs, {items_in_both} items in both lists")
        
        # Convert to list and sort by combined_score (highest first)
        combined_results = list(results_dict.values())
        print(f"🔍 Combined search: {len(combined_results)} unique results before sort")
        combined_results.sort(key=lambda x: x.get("combined_score", 0.0) or 0.0, reverse=True)
        combined_results = combined_results[:top_n]  # Limit to top_n
        
        print(f"🔍 Combined search: {len(combined_results)} results after sort and limit")
        if combined_results:
            print(f"   Top 3 combined scores: {[r.get('combined_score', 0.0) for r in combined_results[:3]]}")
            print(f"   Top 3 result IDs: {[r.get('id', 'N/A')[:8] for r in combined_results[:3]]}")
            print(f"   Top 3 vector scores: {[r.get('vector_score', 'None') for r in combined_results[:3]]}")
            print(f"   Top 3 topic scores: {[r.get('topic_entity_score', 'None') for r in combined_results[:3]]}")
        
        # Convert to SearchResultItem format
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=q.get("questionText", ""),
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=q.get("video_link"),
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", 0),
                score=q.get("combined_score"),  # Show combined score
                vector_score=q.get("vector_score"),  # Show vector score
                topic_entity_score=q.get("topic_entity_score")  # Show topic score
            )
        
        return CombinedSearchResponse(
            query=query,
            results=[convert_to_result_item(q) for q in combined_results],
            total_questions_in_db=total_count
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in combined search: {str(e)}")


@router.get("/search/count")
async def get_total_questions_count():
    """
    Get the total number of questions in the database.
    Does not perform any searches.
    """
    try:
        from app.services.cosmos_service import get_cosmos_container
        container = get_cosmos_container()
        count_query = "SELECT VALUE COUNT(1) FROM c"
        try:
            total_count = list(container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))[0]
        except Exception as e:
            print(f"Warning: Could not get total count: {e}")
            total_count = 0
        return {"total_questions_in_db": total_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting total count: {str(e)}")


@router.get("/search/compare", response_model=SearchComparisonResponse)
async def compare_search_methods(
    query: str = Query(..., description="Search query"),
    top_n: int = Query(10, ge=1, le=50, description="Number of results per method")
):
    """
    Compare search methods:
    1. Vector (semantic) search
    2. Topic/Entity search
    
    Returns separate arrays of results for manual comparison.
    """
    try:
        # Get total count of questions in DB using a simple COUNT query
        from app.services.cosmos_service import get_cosmos_container
        container = get_cosmos_container()
        count_query = "SELECT VALUE COUNT(1) FROM c"
        try:
            total_count = list(container.query_items(
                query=count_query,
                enable_cross_partition_query=True
            ))[0]
        except Exception as e:
            print(f"Warning: Could not get total count: {e}")
            total_count = 0
        
        # Run all search methods
        results = search_all_methods(query, top_n)
        
        # Convert to response format
        def convert_to_result_item(q: Dict) -> SearchResultItem:
            return SearchResultItem(
                id=q.get("id", ""),
                questionText=q.get("questionText", q.get("question", "")),
                domain=q.get("domain"),
                topics=q.get("topics", []),
                entities=q.get("entities", []),
                video_link=q.get("video_link"),
                full_video_link=q.get("full_video_link"),
                playlist_link=q.get("playlist_link"),
                voteUp=q.get("voteUp", q.get("votes", q.get("upvotes", 0))),
                score=q.get("bm25_score") or q.get("topic_entity_score") or q.get("vector_score")
            )
        
        return SearchComparisonResponse(
            query=query,
            vector_results=[convert_to_result_item(q) for q in results["vector_results"]],
            topic_entity_results=[convert_to_result_item(q) for q in results["topic_entity_results"]],
            total_questions_in_db=total_count
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in search comparison: {str(e)}")

@router.post("/questions/queue")
async def add_question_to_queue_endpoint(request: QueueQuestionRequest):
    """
    Add a question to the queue for future answers.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        question_doc = add_question_to_queue(
            question=question,
            domain=request.domain,
            video_link=request.video_link,
            full_video_link=request.full_video_link,
            playlist_link=request.playlist_link,
            tags=request.tags,
            embedding=request.embedding,
            embedding_model=request.embedding_model,
            embedding_dim=request.embedding_dim
        )
        votes = question_doc.get("voteUp", question_doc.get("votes", question_doc.get("upvotes", 0)))
        return {
            "message": "Question added to queue" if votes == 0 else "Question already in queue",
            "question": question_doc.get("questionText", question_doc.get("question")),
            "upvotes": votes,
            "id": question_doc.get("id"),
            "created_at": question_doc.get("createdAt", question_doc.get("created_at")),
            "domain": question_doc.get("domain"),
            "canonical_text": question_doc.get("canonical_text"),
            "topics": question_doc.get("topics", []),
            "entities": question_doc.get("entities", []),
            "tags": question_doc.get("tags", []),
            "timesAsked": question_doc.get("timesAsked", 1),
            "status": question_doc.get("status", "active")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding question to queue: {str(e)}")

@router.post("/questions/upvote")
async def upvote_question_endpoint(request: UpvoteQuestionRequest):
    """
    Upvote a question in the queue. Creates it if it doesn't exist.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    try:
        question_doc = upvote_question(question)
        return {
            "message": "Question upvoted",
            "question": question_doc.get("question"),
            "upvotes": question_doc.get("voteUp", question_doc.get("votes", question_doc.get("upvotes", 0))),
            "id": question_doc.get("id"),
            "updated_at": question_doc.get("updated_at")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error upvoting question: {str(e)}")

@router.get("/questions/queue")
async def get_question_queue_endpoint(
    limit: Optional[int] = Query(50, ge=1, le=100, description="Maximum number of questions to return"),
    sort_by: Optional[str] = Query("upvotes", description="Sort by 'upvotes' or 'created_at'")
):
    """
    Get all questions in the queue, sorted by upvotes or creation date.
    """
    try:
        questions = get_questions_queue(limit=limit, sort_by=sort_by or "upvotes")
        return {
            "questions": questions,
            "total": len(questions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching questions: {str(e)}")

@router.get("/answers/v1/queue-info", response_model=QueueInfo)
async def get_queue_info(
    question: str = Query(..., description="User's question")
):
    """
    Get full queue information for a question, including similar questions to upvote.
    
    This endpoint should be called when the user clicks "show queue" to display:
    - Similar questions from the database/queue that they can upvote
    - Whether their question is already in the queue
    - Current upvote count for their question
    - Option to submit their own question
    
    Returns similar questions (up to 5) that are related to the user's question,
    sorted by upvotes, so users can upvote existing similar questions instead of
    creating duplicates.
    """
    try:
        return _build_queue_info(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building queue info: {str(e)}")