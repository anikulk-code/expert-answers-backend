#!/usr/bin/env python3
"""Simple script to migrate questions from JSON to Cosmos DB."""

import os
import sys
import json
import argparse
import uuid
from typing import Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container
from app.services.question_processor import process_question
from app.services.llm_service import get_playlist_id


def extract_video_info(url: str) -> Dict[str, Optional[str]]:
    """Extract video link and full video link from URL."""
    if not url:
        return {
            "video_link": None,
            "full_video_link": None,
            "playlist_link": None
        }
    
    # Extract base URL (without timestamp)
    if '&t=' in url:
        full_video_link = url.split('&t=')[0]
    elif '?t=' in url:
        full_video_link = url.split('?t=')[0]
    else:
        full_video_link = url
    
    # Extract video ID for playlist lookup
    video_id = None
    if 'watch?v=' in full_video_link:
        video_id = full_video_link.split('watch?v=')[1].split('&')[0]
    
    # Get playlist ID if available
    playlist_link = None
    if video_id:
        try:
            playlist_id = get_playlist_id(video_id)
            if playlist_id:
                playlist_link = f"https://www.youtube.com/playlist?list={playlist_id}"
        except Exception:
            pass  # Silently fail - playlist lookup is optional
    
    return {
        "video_link": url,  # Original URL with timestamp
        "full_video_link": full_video_link,
        "playlist_link": playlist_link
    }

def main():
    parser = argparse.ArgumentParser(description="Migrate questions to Cosmos (with optional limit).")
    parser.add_argument("--questions-file", type=str, default="askswami_questions.json", help="Path to questions JSON")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of questions to process (e.g., 1)")
    args = parser.parse_args()

    # Load questions
    questions_file = args.questions_file
    if not os.path.exists(questions_file):
        print(f"❌ File not found: {questions_file}")
        return
    
    print(f"Loading {questions_file}...")
    with open(questions_file, 'r') as f:
        questions = json.load(f)

    if args.limit:
        questions = questions[: args.limit]
        print(f"Processing {len(questions)} question(s) (limit set)\n")
    else:
        print(f"Found {len(questions)} questions\n")
    
    # Get container
    container = get_cosmos_container()
    print("✓ Connected to Cosmos DB")
    
    # Test connection by checking container exists
    try:
        props = container.read()
        print(f"✓ Container '{props.get('id')}' found\n")
    except Exception as e:
        print(f"❌ Cannot access container: {e}")
        print("\nCheck:")
        print("1. Container name matches AZURE_COSMOS_CONTAINER_NAME in .env")
        print("2. Cosmos DB key is correct (Primary Key, not Read-only)")
        print("3. Container exists in Azure Portal")
        return
    
    # Process questions
    success = 0
    skipped = 0
    errors = 0
    
    for i, q_data in enumerate(questions, 1):
        question_text = q_data.get("question", "").strip()
        
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{len(questions)}] {question_text[:60]}...")
        
        try:
            # Extract video information from URL field
            url = q_data.get("url", "")
            video_info = extract_video_info(url)
            
            # Process question (computes canonical_text, topics, entities)
            processed = process_question(question_text)
            
            # Generate ID if missing
            question_id = q_data.get("id") or str(uuid.uuid4())
            if not question_id or question_id.strip() == "":
                question_id = str(uuid.uuid4())
            
            # Create document
            doc = {
                "id": str(question_id),
                "questionText": question_text,
                "normalizedText": question_text.lower().strip(),
                "domain": q_data.get("domain", "philosophy"),
                "topics": processed.get("topics", []),
                "entities": processed.get("entities", []),
                "video_link": video_info["video_link"],
                "full_video_link": video_info["full_video_link"],
                "playlist_link": video_info["playlist_link"],
                "voteUp": q_data.get("voteUp", 0),
                "timesAsked": q_data.get("timesAsked", 1),
                "status": "active"
            }
            
            # Add canonical_text if available
            if processed.get("canonical_text"):
                doc["canonical_text"] = processed["canonical_text"]
            
            # Check if exists using query (safer than read_item)
            check_query = f"SELECT c.id FROM c WHERE c.id = '{doc['id']}'"
            existing = list(container.query_items(query=check_query, enable_cross_partition_query=True))
            
            if existing:
                skipped += 1
                continue
            
            # Create item
            container.create_item(body=doc)
            success += 1
            
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # If item already exists, skip it
            if "Conflict" in error_type or "409" in error_msg:
                skipped += 1
                continue
            
            errors += 1
            print(f"  ✗ Error ({error_type}): {error_msg[:200]}")
    
    print(f"\n✅ Done!")
    print(f"   Success: {success}")
    print(f"   Skipped: {skipped}")
    print(f"   Errors: {errors}")

if __name__ == "__main__":
    main()
