#!/usr/bin/env python3
"""
Script to delete all questions from Cosmos DB.

WARNING: This will permanently delete all questions in the database.
Use with caution!
"""

import os
import sys
import argparse
from typing import List, Dict

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container


def delete_all_questions(dry_run: bool = False) -> Dict:
    """
    Delete all questions from Cosmos DB.
    
    Args:
        dry_run: If True, don't actually delete, just show what would be deleted
    
    Returns:
        Dictionary with deletion statistics
    """
    container = get_cosmos_container()
    
    # Get all questions
    print("Fetching all questions from Cosmos DB...")
    query = "SELECT * FROM c"
    questions = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    total_count = len(questions)
    print(f"Found {total_count} questions\n")
    
    if total_count == 0:
        print("No questions to delete.")
        return {"total": 0, "deleted": 0, "errors": 0}
    
    if dry_run:
        print("🔍 DRY RUN MODE - No questions will be deleted\n")
        print("Questions that would be deleted:")
        for i, q in enumerate(questions[:10], 1):
            question_text = q.get("questionText", q.get("question", "N/A"))
            print(f"  {i}. {question_text[:70]}")
        if total_count > 10:
            print(f"  ... and {total_count - 10} more")
        return {"total": total_count, "deleted": 0, "errors": 0}
    
    # Confirm deletion
    print(f"⚠️  WARNING: This will delete ALL {total_count} questions!")
    print("This action cannot be undone.\n")
    confirm = input("Type 'DELETE ALL' to confirm: ")
    
    if confirm != "DELETE ALL":
        print("Deletion cancelled.")
        return {"total": total_count, "deleted": 0, "errors": 0, "cancelled": True}
    
    print("\nDeleting questions...\n")
    
    stats = {
        "total": total_count,
        "deleted": 0,
        "errors": 0
    }
    
    # Delete each question
    for i, question in enumerate(questions, 1):
        question_id = question.get("id")
        question_text = question.get("questionText", question.get("question", "N/A"))
        
        # Show progress every 10 questions
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{total_count}] Deleting: {question_text[:60]}...")
        
        try:
            container.delete_item(
                item=question_id,
                partition_key=question_id
            )
            stats["deleted"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"  ✗ Error deleting question {question_id}: {e}")
    
    print("\n" + "="*60)
    print("DELETION SUMMARY")
    print("="*60)
    print(f"Total questions: {stats['total']}")
    print(f"✓ Successfully deleted: {stats['deleted']}")
    print(f"✗ Errors: {stats['errors']}")
    
    return stats


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Delete all questions from Cosmos DB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
WARNING: This script will permanently delete all questions from Cosmos DB.
Use --dry-run to preview what would be deleted without actually deleting.
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (use with caution!)"
    )
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("="*60)
        print("DRY RUN MODE - Preview Only")
        print("="*60 + "\n")
    else:
        print("="*60)
        print("DELETE ALL QUESTIONS FROM COSMOS DB")
        print("="*60 + "\n")
    
    try:
        stats = delete_all_questions(dry_run=args.dry_run)
        
        if not args.dry_run and stats.get("deleted", 0) > 0:
            print(f"\n✅ Successfully deleted {stats['deleted']} questions from Cosmos DB")
        elif args.dry_run:
            print(f"\n🔍 Dry run complete. Run without --dry-run to actually delete.")
        
    except KeyboardInterrupt:
        print("\n\nDeletion cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
