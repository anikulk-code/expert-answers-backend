from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel
import json
import os
from pathlib import Path

router = APIRouter()

# Cache for tagged chapters
_tagged_chapters_cache = None

def load_tagged_chapters() -> List[Dict[str, Any]]:
    """Load tagged chapters from JSON file."""
    global _tagged_chapters_cache
    
    if _tagged_chapters_cache is not None:
        return _tagged_chapters_cache
    
    # Try to load from backend directory first, then Downloads
    json_paths = [
        Path(__file__).parent.parent.parent / "askswami_chapters_tagged.json",
        Path.home() / "Downloads" / "askswami_chapters_tagged.json"
    ]
    
    for json_path in json_paths:
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    _tagged_chapters_cache = json.load(f)
                    return _tagged_chapters_cache
            except Exception as e:
                print(f"Error loading {json_path}: {e}")
                continue
    
    raise HTTPException(
        status_code=404,
        detail="Tagged chapters file not found. Please ensure askswami_chapters_tagged.json exists."
    )


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
    """Get all available tags with question counts."""
    chapters = load_tagged_chapters()
    
    # Count questions per tag
    tag_counts: Dict[str, int] = {}
    for chapter in chapters:
        primary_tag = chapter.get("primary_tag", "Other")
        tag_counts[primary_tag] = tag_counts.get(primary_tag, 0) + 1
    
    # Convert to list and sort by count (descending)
    tags = [
        TagInfo(tag=tag, count=count)
        for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    return tags


@router.get("/tags/{tag}/questions", response_model=List[TaggedQuestion])
async def get_questions_by_tag(tag: str):
    """Get all questions for a specific tag."""
    chapters = load_tagged_chapters()
    
    # Filter chapters by primary tag (case-insensitive)
    matching_chapters = [
        chapter for chapter in chapters
        if chapter.get("primary_tag", "").lower() == tag.lower()
    ]
    
    if not matching_chapters:
        return []
    
    # Convert to response format
    questions = []
    for chapter in matching_chapters:
        questions.append(TaggedQuestion(
            question=chapter.get("chapter_title", ""),
            url=chapter.get("chapter_url", ""),
            timestamp=chapter.get("chapter_timestamp", ""),
            video_title=chapter.get("video_title", ""),
            primary_tag=chapter.get("primary_tag", ""),
            tags=chapter.get("tags", [])
        ))
    
    return questions

