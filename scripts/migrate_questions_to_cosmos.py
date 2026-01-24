#!/usr/bin/env python3
"""
Migration script to store questions from askswami_questions.json into Cosmos DB.

This script:
1. Loads questions from the JSON file
2. Processes each question to compute canonical_text, topics, and entities
3. Extracts video links and playlist information
4. Stores questions in Cosmos DB with the new schema
5. Skips questions that already exist (based on normalizedText)
6. Provides progress feedback and error handling
"""

import os
import sys
import json
import time
from typing import Dict, List, Optional
from datetime import datetime, timezone

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import uuid

from app.services.cosmos_service import (
    get_cosmos_container,
    normalize_question,
    find_question_by_text
)
from app.services.question_processor import process_question
from app.services.llm_service import get_playlist_id


def extract_video_info(url: str) -> Dict[str, Optional[str]]:
    """
    Extract video link and full video link from URL.
    
    Args:
        url: YouTube URL with timestamp (e.g., "https://youtube.com/watch?v=VIDEO_ID&t=1234s")
    
    Returns:
        Dictionary with video_link (with timestamp) and full_video_link (without timestamp)
    """
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
        except Exception as e:
            # Silently fail - playlist lookup is optional
            pass
    
    return {
        "video_link": url,  # Original URL with timestamp
        "full_video_link": full_video_link,
        "playlist_link": playlist_link
    }


def migrate_question(question_data: Dict, container, dry_run: bool = False) -> Dict:
    """
    Migrate a single question to Cosmos DB.
    
    Args:
        question_data: Question data from JSON file
        container: Cosmos DB container
        dry_run: If True, don't actually write to Cosmos DB
    
    Returns:
        Dictionary with migration result
    """
    try:
        question_text = question_data.get("question", "").strip()
        if not question_text:
            return {"status": "skipped", "reason": "Empty question"}
        
        # Check if question already exists
        try:
            existing = find_question_by_text(question_text)
            if existing:
                return {"status": "skipped", "reason": "Already exists", "id": existing.get("id")}
        except Exception as e:
            # If check fails, continue anyway (might be first run)
            print(f"  Warning: Could not check if question exists: {e}")
        
        # Extract video information
        url = question_data.get("url", "")
        try:
            video_info = extract_video_info(url)
        except Exception as e:
            print(f"  Warning: Error extracting video info: {e}")
            video_info = {
                "video_link": url if url else None,
                "full_video_link": url.split('&t=')[0] if '&t=' in url else (url.split('?t=')[0] if '?t=' in url else url) if url else None,
                "playlist_link": None
            }
        
        # Process question to get computed values
        try:
            processed = process_question(question_text)
            canonical_text = processed["canonical_text"]
            topics = processed["topics"]
            entities = processed["entities"]
        except Exception as e:
            print(f"  Warning: Error processing question with LLM: {e}")
            import traceback
            traceback.print_exc()
            # Fallback values
            canonical_text = question_text.lower()
            topics = []
            entities = []
        
        # Create document with new schema
        question_normalized = normalize_question(question_text)
        question_id = str(uuid.uuid4()) if not dry_run else "dry-run-id"
        
        question_doc = {
            "id": question_id,
            "domain": "philosophy",  # All questions are Vedanta/philosophy
            "questionText": question_text,
            "normalizedText": question_normalized,
            "canonical_text": canonical_text,
            "topics": topics,
            "entities": entities,
            "tags": [],  # Can be populated later
            "video_link": video_info["video_link"],
            "full_video_link": video_info["full_video_link"],
            "playlist_link": video_info["playlist_link"],
            "embedding": None,  # Will be populated when we add vector search
            "embeddingModel": None,
            "embeddingDim": None,
            "voteUp": 0,
            "timesAsked": 1,
            "status": "active",
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            # Backward compatibility fields
            "question": question_text,
            "question_normalized": question_normalized,
            "votes": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if not dry_run:
            try:
                container.create_item(body=question_doc)
                return {"status": "success", "id": question_id}
            except Exception as e:
                return {"status": "error", "error": str(e), "error_type": type(e).__name__}
        else:
            return {"status": "dry_run", "id": question_id}
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "error_details": error_details
        }


def main():
    """Main migration function"""
    import argparse
    import uuid
    
    parser = argparse.ArgumentParser(description="Migrate questions to Cosmos DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually writing to Cosmos DB"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of questions to process (for testing)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip questions that already exist (default: True)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of questions to process before showing progress (default: 10)"
    )
    parser.add_argument(
        "--questions-file",
        type=str,
        default="askswami_questions.json",
        help="Path to questions JSON file (default: askswami_questions.json)"
    )
    
    args = parser.parse_args()
    
    # Load questions from JSON
    questions_file = args.questions_file
    if not os.path.exists(questions_file):
        print(f"Error: Questions file not found: {questions_file}")
        sys.exit(1)
    
    print(f"Loading questions from {questions_file}...")
    with open(questions_file, 'r') as f:
        questions = json.load(f)
    
    total_questions = len(questions)
    if args.limit:
        questions = questions[:args.limit]
        print(f"Limited to {len(questions)} questions (out of {total_questions} total)")
    else:
        print(f"Found {total_questions} questions")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be written to Cosmos DB\n")
    
    # Get Cosmos DB container
    try:
        container = get_cosmos_container()
        print("✓ Connected to Cosmos DB\n")
    except Exception as e:
        print(f"Error connecting to Cosmos DB: {e}")
        sys.exit(1)
    
    # Migration stats
    stats = {
        "total": len(questions),
        "success": 0,
        "skipped": 0,
        "errors": 0
    }
    
    start_time = time.time()
    
    print("Starting migration...\n")
    
    for i, question_data in enumerate(questions, 1):
        question_text = question_data.get("question", "").strip()
        
        # Progress indicator
        if i % args.batch_size == 0 or i == 1:
            print(f"[{i}/{len(questions)}] Processing: {question_text[:60]}...")
        
        try:
            result = migrate_question(question_data, container, dry_run=args.dry_run)
        except Exception as e:
            import traceback
            stats["errors"] += 1
            print(f"  ✗ Fatal Error: {type(e).__name__}: {str(e)}")
            print(f"    Question: {question_text[:80]}")
            if i <= 3:  # Show traceback for first 3 errors
                print(f"    Traceback: {traceback.format_exc()[:300]}...")
            continue
        
        if result["status"] == "success":
            stats["success"] += 1
            if i % args.batch_size == 0:
                print(f"  ✓ Added to Cosmos DB (ID: {result['id'][:8]}...)")
        elif result["status"] == "dry_run":
            stats["success"] += 1
            if i % args.batch_size == 0:
                print(f"  ✓ Would be added to Cosmos DB (dry run)")
        elif result["status"] == "skipped":
            stats["skipped"] += 1
            if i % args.batch_size == 0:
                print(f"  ⊘ Skipped: {result.get('reason', 'Unknown')}")
        else:
            stats["errors"] += 1
            error_msg = result.get('error', 'Unknown error')
            error_type = result.get('error_type', 'Unknown')
            print(f"  ✗ Error ({error_type}): {error_msg}")
            print(f"    Question: {question_text[:80]}")
            # Print full traceback if available (for debugging)
            if result.get('error_details') and i <= 3:  # Only show first 3 detailed errors
                print(f"    Details: {result['error_details'][:200]}...")
        
        # Small delay to avoid rate limiting (especially for LLM calls)
        if i % 10 == 0:
            time.sleep(0.5)  # Brief pause every 10 questions
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"Total questions processed: {stats['total']}")
    print(f"✓ Successfully migrated: {stats['success']}")
    print(f"⊘ Skipped (already exist): {stats['skipped']}")
    print(f"✗ Errors: {stats['errors']}")
    print(f"⏱️  Time elapsed: {elapsed_time:.2f} seconds")
    if stats['success'] > 0:
        print(f"⚡ Average time per question: {elapsed_time/stats['success']:.2f} seconds")
    
    if args.dry_run:
        print("\n⚠️  This was a DRY RUN - no data was written to Cosmos DB")
    else:
        print(f"\n✅ Migration complete! {stats['success']} questions stored in Cosmos DB")


if __name__ == "__main__":
    main()
