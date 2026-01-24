from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.services.cosmos_service import get_cosmos_container
from app.services.youtube_service import get_video_thumbnail
from app.services.llm_service import get_playlist_id

router = APIRouter()

# Static list of main tags (topics with 5+ questions, derived from DB analysis)
# These are the lowercase topic names as they appear in the database
MAIN_TAGS_DB = [
    'consciousness',
    'philosophy',
    'meditation',
    'enlightenment',
    'advaita',
    'karma',
    'suffering',
    'maya',
    'mind',
    'sleep',
    'artificial intelligence',
    'buddhism',
    'theology',
    'bhakti',
    'reality',
    'realization',
    'reincarnation',
    'experience',
    'free will',
    'mindfulness',
    'non-duality',
    'personal development',
    'prayer',
    'science',
    'spiritual life',
    'spiritual practice',
    'universe',
    'yoga',
]

def get_main_tags() -> List[str]:
    """Get list of main tags (static list derived from DB analysis)."""
    return MAIN_TAGS_DB


def _extract_timestamp_from_url(video_link: str) -> str:
    """Extract timestamp from YouTube URL (format: &t=123s)."""
    if not video_link or '&t=' not in video_link:
        return ''
    try:
        time_part = video_link.split('&t=')[1].split('s')[0]
        seconds = int(time_part)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    except:
        return ''


def normalize_topic_name(topic: str) -> str:
    """Normalize topic name for display (capitalize properly)."""
    topic_name_map = {
        'artificial intelligence': 'AI',
        'consciousness': 'Consciousness',
        'philosophy': 'Philosophy',
        'meditation': 'Meditation',
        'enlightenment': 'Enlightenment',
        'advaita': 'Advaita',
        'karma': 'Karma',
        'suffering': 'Suffering & Ethics',
        'ethics': 'Suffering & Ethics',
        'maya': 'Maya',
        'mind': 'Mind',
        'sleep': 'Sleep',
        'buddhism': 'Buddhism',
        'theology': 'Theology',
        'bhakti': 'God & Devotion',
        'devotion': 'God & Devotion',
        'reality': 'Reality',
        'realization': 'Realization',
        'reincarnation': 'Reincarnation',
        'experience': 'Experience',
        'free will': 'Free Will',
        'mindfulness': 'Mindfulness',
        'non-duality': 'Non-Duality',
        'personal development': 'Personal Development',
        'prayer': 'Prayer',
        'science': 'Science',
        'spiritual life': 'Spiritual Life',
        'spiritual practice': 'Spiritual Practice',
        'universe': 'Universe',
        'yoga': 'Yoga',
    }
    return topic_name_map.get(topic.lower(), topic.title())


class TagInfo(BaseModel):
    tag: str
    count: int


class TaggedQuestion(BaseModel):
    question: str
    url: str
    timestamp: str
    video_title: str
    primary_tag: str
    tags: List[str]


@router.get("/tags", response_model=List[TagInfo])
async def get_tags():
    """Get all available tags with question counts from Cosmos DB."""
    try:
        container = get_cosmos_container()
        main_tags = get_main_tags()
        
        # Count questions for each main tag using COUNT queries (fast)
        tag_counts: Dict[str, int] = {}
        
        for main_topic in main_tags:
            query = """
            SELECT VALUE COUNT(1)
            FROM c
            WHERE ARRAY_CONTAINS(c.topics, @topic, true)
              AND IS_DEFINED(c.video_link) 
              AND c.video_link != null 
              AND c.video_link != ''
            """
            parameters = [{"name": "@topic", "value": main_topic}]
            
            try:
                result = list(container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True
                ))
                count = result[0] if result else 0
                if count > 0:
                    normalized_tag = normalize_topic_name(main_topic)
                    tag_counts[normalized_tag] = count
            except Exception as e:
                print(f"Error counting tag {main_topic}: {e}")
                import traceback
                print(traceback.format_exc())
                continue
        
        # Count "Other" - questions that don't have any main tag
        # We need to query all questions and filter in Python (Cosmos DB doesn't support NOT ARRAY_CONTAINS easily)
        # But we can optimize by only fetching topics field
        # NOTE: This query can be slow if there are many questions. Consider pagination or caching.
        query = """
        SELECT c.topics 
        FROM c 
        WHERE IS_DEFINED(c.topics) 
          AND IS_ARRAY(c.topics) = true
          AND IS_DEFINED(c.video_link) 
          AND c.video_link != null 
          AND c.video_link != ''
        """
        
        try:
            print("Counting 'Other' tag - this may take a moment...")
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            print(f"Fetched {len(items)} items for 'Other' count")
            
            other_count = 0
            for item in items:
                topics = item.get('topics', [])
                if not isinstance(topics, list):
                    continue
                
                # Check if question has any main tag
                has_main_tag = False
                for topic in topics:
                    if topic and topic.lower().strip() in main_tags:
                        has_main_tag = True
                        break
                
                if not has_main_tag:
                    other_count += 1
            
            if other_count > 0:
                tag_counts['Other'] = other_count
                print(f"Found {other_count} questions in 'Other' category")
        except Exception as e:
            print(f"Error counting Other: {e}")
            import traceback
            print(traceback.format_exc())
        
        # Convert to list and sort
        tags_list = [
            TagInfo(tag=tag, count=count)
            for tag, count in tag_counts.items()
        ]
        
        # Sort alphabetically, but put "Other" at the end
        def sort_key(tag_info):
            if tag_info.tag.lower() == "other":
                return (1, tag_info.tag.lower())
            return (0, tag_info.tag.lower())
        
        tags = sorted(tags_list, key=sort_key)
        print(f"Returning {len(tags)} tags")
        return tags
    
    except Exception as e:
        print(f"Error in get_tags endpoint: {e}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error fetching tags: {str(e)}")


@router.get("/tags/{tag}/questions", response_model=List[Dict])
async def get_questions_by_tag(tag: str, include_thumbnails: bool = Query(False, description="Include thumbnails (slower but better UX)")):
    """Get all questions for a specific tag from Cosmos DB."""
    container = get_cosmos_container()
    main_tags = get_main_tags()
    
    tag_lower = tag.lower()
    
    # Handle "Other" tag - questions that don't have any main tags
    if tag_lower == "other":
        # Build query to exclude all main tags
        query = """
        SELECT c.id, c.questionText, c.video_link, c.topics
        FROM c
        WHERE IS_DEFINED(c.video_link) 
          AND c.video_link != null 
          AND c.video_link != ''
          AND IS_DEFINED(c.topics) 
          AND IS_ARRAY(c.topics) = true
        """
        
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        # Filter out questions that have any main tag
        other_questions = []
        for item in items:
            topics = item.get('topics', [])
            has_main_tag = False
            for topic in topics:
                if topic and topic.lower() in main_tags:
                    has_main_tag = True
                    break
            if not has_main_tag:
                other_questions.append(item)
        
        questions = []
        for item in other_questions:
            # Extract timestamp from video_link if present
            video_link = item.get('video_link', '')
            base_url = video_link.split('&t=')[0] if '&t=' in video_link else video_link
            video_id = base_url.split('watch?v=')[1] if 'watch?v=' in base_url else None
            timestamp = _extract_timestamp_from_url(video_link)
            
            # Get thumbnail and playlist_id only if requested
            thumbnail = None
            playlist_id = None
            if include_thumbnails and video_id:
                thumbnail = get_video_thumbnail(video_id)
                playlist_id = get_playlist_id(video_id)
            
            questions.append({
                "videoLink": base_url,
                "time": timestamp,
                "speakers": "Sarvapriyananda",
                "date": "2024-01-01",  # Placeholder
                "region": None,
                "score": None,
                "answerViewPoint": None,
                "thumbnail": thumbnail,
                "questionTitle": item.get('questionText', ''),
                "playlistId": playlist_id
            })
        
        return questions
    
    # For specific tags, find matching topic in main_tags
    matching_topic = None
    for main_topic in main_tags:
        if normalize_topic_name(main_topic).lower() == tag_lower:
            matching_topic = main_topic
            break
    
    if not matching_topic:
        return []
    
    # Query for questions with this topic in their topics array
    query = """
    SELECT c.id, c.questionText, c.video_link, c.topics
    FROM c
    WHERE ARRAY_CONTAINS(c.topics, @topic, true)
      AND IS_DEFINED(c.video_link) 
      AND c.video_link != null 
      AND c.video_link != ''
    """
    
    parameters = [{"name": "@topic", "value": matching_topic}]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    # Convert to response format (AnswerResponse format)
    questions = []
    for item in items:
        video_link = item.get('video_link', '')
        base_url = video_link.split('&t=')[0] if '&t=' in video_link else video_link
        video_id = base_url.split('watch?v=')[1] if 'watch?v=' in base_url else None
        timestamp = _extract_timestamp_from_url(video_link)
        
        # Get thumbnail and playlist_id only if requested
        thumbnail = None
        playlist_id = None
        if include_thumbnails and video_id:
            thumbnail = get_video_thumbnail(video_id)
            playlist_id = get_playlist_id(video_id)
        
        questions.append({
            "videoLink": base_url,
            "time": timestamp,
            "speakers": "Sarvapriyananda",
            "date": "2024-01-01",  # Placeholder
            "region": None,
            "score": None,
            "answerViewPoint": None,
            "thumbnail": thumbnail,
            "questionTitle": item.get('questionText', ''),
            "playlistId": playlist_id
        })
    
    return questions


@router.get("/tags/search", response_model=List[Dict])
async def search_questions_by_topic(query: str, include_thumbnails: bool = Query(False, description="Include thumbnails (slower but better UX)")):
    """Search questions by topic/keyword in Cosmos DB."""
    if not query or not query.strip():
        return []
    
    container = get_cosmos_container()
    query_lower = query.lower().strip()
    query_words = query_lower.split()
    
    # Build query to search in topics array and question text
    # We'll do case-insensitive matching in Python for now
    # (Cosmos DB ARRAY_CONTAINS with true flag does case-insensitive, but we need partial matching)
    
    sql_query = """
    SELECT c.id, c.questionText, c.video_link, c.topics
    FROM c
    WHERE IS_DEFINED(c.video_link) 
      AND c.video_link != null 
      AND c.video_link != ''
      AND IS_DEFINED(c.topics) 
      AND IS_ARRAY(c.topics) = true
    """
    
    items = list(container.query_items(
        query=sql_query,
        enable_cross_partition_query=True
    ))
    
    # Filter in Python for flexible matching
    matching_items = []
    for item in items:
        question_text = item.get('questionText', '').lower()
        topics = item.get('topics', [])
        topics_lower = [t.lower() if t else '' for t in topics]
        
        matches = False
        
        # Check if all query words are in question text
        if all(word in question_text for word in query_words):
            matches = True
        
        # Check if query matches any topic (case-insensitive, partial match)
        if not matches:
            for topic in topics_lower:
                if query_lower in topic or topic in query_lower:
                    matches = True
                    break
        
        # Check if any query word matches any topic
        if not matches:
            for word in query_words:
                if any(word in topic for topic in topics_lower):
                    matches = True
                    break
        
        if matches:
            matching_items.append(item)
    
    # Convert to response format (AnswerResponse format)
    questions = []
    
    # Fetch thumbnails sequentially if requested (safer than parallel, avoids SSL issues)
    if include_thumbnails and matching_items:
        for item in matching_items:
            video_link = item.get('video_link', '')
            base_url = video_link.split('&t=')[0] if '&t=' in video_link else video_link
            video_id = base_url.split('watch?v=')[1] if 'watch?v=' in base_url else None
            timestamp = _extract_timestamp_from_url(video_link)
            
            thumbnail = None
            playlist_id = None
            if video_id:
                thumbnail = get_video_thumbnail(video_id)
                playlist_id = get_playlist_id(video_id)
            
            questions.append({
                "videoLink": base_url,
                "time": timestamp,
                "speakers": "Sarvapriyananda",
                "date": "2024-01-01",  # Placeholder
                "region": None,
                "score": None,
                "answerViewPoint": None,
                "thumbnail": thumbnail,
                "questionTitle": item.get('questionText', ''),
                "playlistId": playlist_id
            })
    else:
        # Fast path: skip thumbnails
        for item in matching_items:
            video_link = item.get('video_link', '')
            base_url = video_link.split('&t=')[0] if '&t=' in video_link else video_link
            timestamp = _extract_timestamp_from_url(video_link)
            
            questions.append({
                "videoLink": base_url,
                "time": timestamp,
                "speakers": "Sarvapriyananda",
                "date": "2024-01-01",  # Placeholder
                "region": None,
                "score": None,
                "answerViewPoint": None,
                "thumbnail": None,  # Skip thumbnail for faster response
                "questionTitle": item.get('questionText', ''),
                "playlistId": None
            })
    
    return questions


@router.get("/thumbnails/{video_id}")
async def get_thumbnail(video_id: str):
    """
    Get thumbnail URL for a single video ID.
    This endpoint allows progressive loading - frontend can call it for each video
    without blocking the main response.
    """
    thumbnail = get_video_thumbnail(video_id)
    playlist_id = get_playlist_id(video_id) if video_id else None
    
    return {
        "videoId": video_id,
        "thumbnail": thumbnail,
        "playlistId": playlist_id
    }
