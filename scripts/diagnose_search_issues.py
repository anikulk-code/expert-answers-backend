#!/usr/bin/env python3
"""
Diagnostic script to check why search methods are returning no results.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container
from app.services.search_service import bm25_search, vector_search, topic_entity_search


def check_database():
    """Check basic database connectivity and data"""
    print("="*60)
    print("Database Check")
    print("="*60)
    
    container = get_cosmos_container()
    
    # Count total questions
    total_query = "SELECT VALUE COUNT(1) FROM c"
    try:
        total = list(container.query_items(
            query=total_query,
            enable_cross_partition_query=True
        ))[0]
        print(f"✓ Total questions in DB: {total}")
    except Exception as e:
        print(f"✗ Error counting questions: {e}")
        return False
    
    # Count questions with embeddings
    embedding_query = "SELECT VALUE COUNT(1) FROM c WHERE IS_ARRAY(c.embedding) = true AND ARRAY_LENGTH(c.embedding) > 0"
    try:
        with_embeddings = list(container.query_items(
            query=embedding_query,
            enable_cross_partition_query=True
        ))[0]
        print(f"✓ Questions with embeddings: {with_embeddings}")
    except Exception as e:
        print(f"✗ Error counting embeddings: {e}")
    
    # Sample a question
    sample_query = "SELECT TOP 1 c.questionText, c.canonical_text, c.topics, c.entities FROM c"
    try:
        sample = list(container.query_items(
            query=sample_query,
            enable_cross_partition_query=True
        ))
        if sample:
            s = sample[0]
            print(f"\nSample question:")
            print(f"  QuestionText: {s.get('questionText', 'N/A')[:60]}")
            print(f"  Canonical text: {s.get('canonical_text', 'N/A')}")
            print(f"  Topics: {s.get('topics', [])}")
            print(f"  Entities: {len(s.get('entities', []))} entities")
    except Exception as e:
        print(f"✗ Error getting sample: {e}")
    
    return True


def test_bm25_search():
    """Test BM25 search"""
    print("\n" + "="*60)
    print("BM25 Search Test")
    print("="*60)
    
    test_query = "What is the nature of consciousness?"
    print(f"\nTest query: '{test_query}'")
    
    try:
        results = bm25_search(test_query, top_n=5)
        print(f"\nResults: {len(results)} items")
        if results:
            for i, r in enumerate(results[:3], 1):
                score = r.get("bm25_score", 0)
                question = r.get("questionText", r.get("question", ""))
                print(f"  {i}. [Score: {score:.3f}] {question[:70]}")
        else:
            print("  No results returned")
    except Exception as e:
        print(f"✗ BM25 search error: {e}")
        import traceback
        traceback.print_exc()


def test_vector_search():
    """Test vector search"""
    print("\n" + "="*60)
    print("Vector Search Test")
    print("="*60)
    
    test_query = "What is the nature of consciousness?"
    print(f"\nTest query: '{test_query}'")
    
    try:
        results = vector_search(test_query, top_n=5)
        print(f"\nResults: {len(results)} items")
        if results:
            for i, r in enumerate(results[:3], 1):
                score = r.get("vector_score", 0)
                question = r.get("questionText", r.get("question", ""))
                print(f"  {i}. [Score: {score:.4f}] {question[:70]}")
        else:
            print("  No results returned")
    except Exception as e:
        print(f"✗ Vector search error: {e}")
        import traceback
        traceback.print_exc()


def test_topic_entity_search():
    """Test topic/entity search"""
    print("\n" + "="*60)
    print("Topic/Entity Search Test")
    print("="*60)
    
    test_query = "What is the nature of consciousness?"
    print(f"\nTest query: '{test_query}'")
    
    try:
        results = topic_entity_search(test_query, top_n=5)
        print(f"\nResults: {len(results)} items")
        if results:
            for i, r in enumerate(results[:3], 1):
                score = r.get("topic_entity_score", 0)
                question = r.get("questionText", r.get("question", ""))
                topics = r.get("topics", [])
                print(f"  {i}. [Score: {score:.1f}] {question[:70]}")
                if topics:
                    print(f"      Topics: {', '.join(topics[:3])}")
        else:
            print("  No results returned")
    except Exception as e:
        print(f"✗ Topic/Entity search error: {e}")
        import traceback
        traceback.print_exc()


def test_fulltext_search_directly():
    """Test Full Text Search directly"""
    print("\n" + "="*60)
    print("Full Text Search Direct Test")
    print("="*60)
    
    container = get_cosmos_container()
    test_query = "consciousness"
    
    print(f"\nTesting FullTextSearch() with query: '{test_query}'")
    
    try:
        query_sql = """
        SELECT TOP 5
            c.id,
            c.questionText,
            FullTextSearch(c.questionText, @query) AS score
        FROM c
        WHERE FULLTEXTCONTAINS(c.questionText, @query)
        ORDER BY FullTextSearch(c.questionText, @query) DESC
        """
        
        results = list(container.query_items(
            query=query_sql,
            parameters=[{"name": "@query", "value": test_query}],
            enable_cross_partition_query=True
        ))
        
        print(f"\nFullTextSearch() returned {len(results)} results")
        for i, r in enumerate(results[:3], 1):
            score = r.get("score", 0)
            question = r.get("questionText", "N/A")
            print(f"  {i}. [Score: {score:.3f}] {question[:70]}")
    except Exception as e:
        error_msg = str(e)
        print(f"✗ FullTextSearch() error: {error_msg}")
        if "FullTextSearch" in error_msg:
            print("   → Full Text Search feature may not be enabled or Full Text Policy not configured")
        else:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("Search Diagnostic Tool\n")
    
    # Check database
    if not check_database():
        print("\n❌ Database check failed!")
        sys.exit(1)
    
    # Test each search method
    test_bm25_search()
    test_vector_search()
    test_topic_entity_search()
    test_fulltext_search_directly()
    
    print("\n" + "="*60)
    print("Diagnostic Complete")
    print("="*60)
