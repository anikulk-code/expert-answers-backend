#!/usr/bin/env python3
"""
Script to generate and add embeddings to all questions in Cosmos DB.

This script:
1. Fetches all questions from Cosmos DB
2. Generates embeddings using OpenAI's embedding model
3. Updates each question with embedding, embeddingModel, and embeddingDim
4. Skips questions that already have embeddings
5. Provides progress feedback and error handling
"""

import os
import sys
import time
import argparse
from typing import List, Dict, Optional

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container
from app.services.llm_service import get_openai_client


def generate_embedding(text: str, model: str = "text-embedding-3-large") -> Optional[Dict]:
    """
    Generate embedding for a text using OpenAI.
    
    Args:
        text: Text to generate embedding for
        model: Embedding model to use (default: text-embedding-3-large)
    
    Returns:
        Dictionary with embedding, model, and dimension, or None if error
    """
    try:
        openai_client = get_openai_client()
        
        # Use the canonical_text if available, otherwise use questionText
        response = openai_client.embeddings.create(
            model=model,
            input=text
        )
        
        embedding = response.data[0].embedding
        dimension = len(embedding)
        
        return {
            "embedding": embedding,
            "embeddingModel": model,
            "embeddingDim": dimension
        }
    except Exception as e:
        print(f"  Error generating embedding: {e}")
        return None


def get_embedding_text(question: Dict) -> str:
    """
    Get the best text to use for embedding generation.
    Uses full questionText for better semantic understanding.
    
    Args:
        question: Question document from Cosmos DB
    
    Returns:
        Text to use for embedding
    """
    # Use full questionText for better semantic matching
    # canonical_text is too minimal and loses important context
    question_text = question.get("questionText") or question.get("question", "")
    if question_text and question_text.strip():
        return question_text.strip()
    
    # Fallback to canonical_text only if questionText is not available
    canonical_text = question.get("canonical_text")
    if canonical_text and canonical_text.strip():
        return canonical_text
    
    return ""


def add_embeddings_to_questions(
    dry_run: bool = False,
    model: str = "text-embedding-3-large",
    batch_size: int = 10,
    limit: Optional[int] = None,
    skip_existing: bool = True
) -> Dict:
    """
    Add embeddings to all questions in Cosmos DB.
    
    Args:
        dry_run: If True, don't actually update Cosmos DB
        model: Embedding model to use
        batch_size: Show progress every N questions
        limit: Limit number of questions to process (for testing)
        skip_existing: Skip questions that already have embeddings
    
    Returns:
        Dictionary with statistics
    """
    container = get_cosmos_container()
    
    # Query only questions that need embeddings (using Cosmos DB query, not loading all)
    print("Fetching questions from Cosmos DB...")
    if skip_existing:
        # Query for questions without embeddings - use Cosmos DB WHERE clause
        query_sql = """
        SELECT * FROM c 
        WHERE c.embedding = null 
           OR NOT IS_ARRAY(c.embedding) 
           OR ARRAY_LENGTH(c.embedding) = 0
        """
        print("  Querying questions without embeddings...")
    else:
        # Query all questions (for regeneration)
        query_sql = "SELECT * FROM c"
        print("  Querying all questions (will regenerate embeddings)...")
    
    questions = list(container.query_items(
        query=query_sql,
        enable_cross_partition_query=True
    ))
    
    total_count = len(questions)
    
    if skip_existing:
        # Count total questions to show how many were skipped
        try:
            total_query = "SELECT VALUE COUNT(1) FROM c"
            total_all = list(container.query_items(
                query=total_query,
                enable_cross_partition_query=True
            ))[0]
            skipped_count = total_all - total_count
            if skipped_count > 0:
                print(f"  Found {skipped_count} questions that already have embeddings (skipping)")
        except:
            pass
    
    if limit:
        questions = questions[:limit]
        print(f"Limited to {len(questions)} questions (out of {total_count} total)")
    else:
        print(f"Found {total_count} questions without embeddings")
    
    if total_count == 0:
        print("No questions need embeddings.")
        return {"total": 0, "processed": 0, "success": 0, "errors": 0, "skipped": 0}
    
    if dry_run:
        print("\n🔍 DRY RUN MODE - No embeddings will be generated or stored\n")
    
    stats = {
        "total": len(questions),
        "processed": 0,
        "success": 0,
        "errors": 0,
        "skipped": 0
    }
    
    start_time = time.time()
    
    print(f"\nStarting embedding generation (model: {model})...\n")
    
    for i, question in enumerate(questions, 1):
        question_id = question.get("id")
        question_text = get_embedding_text(question)
        
        # Show progress
        if i % batch_size == 0 or i == 1:
            print(f"[{i}/{len(questions)}] Processing: {question_text[:60]}...")
        
        # Generate embedding
        embedding_data = generate_embedding(question_text, model)
        
        if not embedding_data:
            stats["errors"] += 1
            print(f"  ✗ Failed to generate embedding")
            continue
        
        stats["processed"] += 1
        
        if dry_run:
            stats["success"] += 1
            if i % batch_size == 0:
                print(f"  ✓ Would update with embedding (dim: {embedding_data['embeddingDim']})")
            continue
        
        # Update question in Cosmos DB
        try:
            # Update the question document with embedding fields
            question["embedding"] = embedding_data["embedding"]
            question["embeddingModel"] = embedding_data["embeddingModel"]
            question["embeddingDim"] = embedding_data["embeddingDim"]
            question["updatedAt"] = question.get("updatedAt") or question.get("updated_at")
            
            # Replace the item in Cosmos DB
            container.replace_item(item=question_id, body=question)
            stats["success"] += 1
            
            if i % batch_size == 0:
                print(f"  ✓ Updated with embedding (dim: {embedding_data['embeddingDim']})")
        
        except Exception as e:
            stats["errors"] += 1
            print(f"  ✗ Error updating Cosmos DB: {e}")
        
        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print("\n" + "="*60)
    print("EMBEDDING GENERATION SUMMARY")
    print("="*60)
    print(f"Total questions processed: {stats['total']}")
    print(f"✓ Successfully updated: {stats['success']}")
    print(f"✗ Errors: {stats['errors']}")
    print(f"⏱️  Time elapsed: {elapsed_time:.2f} seconds")
    if stats['success'] > 0:
        print(f"⚡ Average time per question: {elapsed_time/stats['success']:.2f} seconds")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN - no embeddings were generated or stored")
    else:
        print(f"\n✅ Embedding generation complete! {stats['success']} questions updated")
    
    return stats


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Generate and add embeddings to questions in Cosmos DB"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually generating or storing embeddings"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="text-embedding-3-large",
        help="Embedding model to use (default: text-embedding-3-large)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of questions to process (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Show progress every N questions (default: 10)"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip questions that already have embeddings (default: True)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate embeddings even if they already exist"
    )
    
    args = parser.parse_args()
    
    if args.force:
        args.skip_existing = False
    
    if args.dry_run:
        print("="*60)
        print("DRY RUN MODE - Preview Only")
        print("="*60 + "\n")
    else:
        print("="*60)
        print("ADD EMBEDDINGS TO QUESTIONS")
        print("="*60 + "\n")
    
    try:
        stats = add_embeddings_to_questions(
            dry_run=args.dry_run,
            model=args.model,
            batch_size=args.batch_size,
            limit=args.limit,
            skip_existing=args.skip_existing
        )
        
    except KeyboardInterrupt:
        print("\n\nEmbedding generation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
