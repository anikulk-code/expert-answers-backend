#!/usr/bin/env python3
"""
Test script to verify vector search is working.
Tests embeddings existence and vector search query.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container
from app.services.vector_search_service import vector_search_cosmos, generate_query_embedding


def test_embeddings_exist():
    """Check if embeddings exist in the database"""
    container = get_cosmos_container()
    
    print("="*60)
    print("Checking Embeddings in Cosmos DB")
    print("="*60)
    
    # Count total questions
    total_query = "SELECT VALUE COUNT(1) FROM c"
    total = list(container.query_items(
        query=total_query,
        enable_cross_partition_query=True
    ))[0]
    print(f"\nTotal questions: {total}")
    
    # Count questions with embeddings
    embedding_query = """
    SELECT VALUE COUNT(1) 
    FROM c 
    WHERE IS_ARRAY(c.embedding) = true 
       AND ARRAY_LENGTH(c.embedding) > 0
    """
    with_embeddings = list(container.query_items(
        query=embedding_query,
        enable_cross_partition_query=True
    ))[0]
    print(f"Questions with embeddings: {with_embeddings}")
    
    # Check embedding models
    model_query = """
    SELECT DISTINCT c.embeddingModel
    FROM c
    WHERE IS_ARRAY(c.embedding) = true 
       AND ARRAY_LENGTH(c.embedding) > 0
    """
    models = list(container.query_items(
        query=model_query,
        enable_cross_partition_query=True
    ))
    print(f"Embedding models found: {[m.get('embeddingModel') for m in models]}")
    
    # Check embedding dimensions
    dim_query = """
    SELECT DISTINCT c.embeddingDim
    FROM c
    WHERE IS_ARRAY(c.embedding) = true 
       AND ARRAY_LENGTH(c.embedding) > 0
    """
    dims = list(container.query_items(
        query=dim_query,
        enable_cross_partition_query=True
    ))
    print(f"Embedding dimensions found: {[d.get('embeddingDim') for d in dims]}")
    
    # Sample a question with embedding
    sample_query = """
    SELECT TOP 1 c.id, c.questionText, c.embeddingModel, c.embeddingDim, ARRAY_LENGTH(c.embedding) as embedding_length
    FROM c
    WHERE IS_ARRAY(c.embedding) = true 
       AND ARRAY_LENGTH(c.embedding) > 0
    """
    sample = list(container.query_items(
        query=sample_query,
        enable_cross_partition_query=True
    ))
    if sample:
        s = sample[0]
        print(f"\nSample question with embedding:")
        print(f"  ID: {s.get('id')}")
        print(f"  Question: {s.get('questionText', 'N/A')[:60]}")
        print(f"  Model: {s.get('embeddingModel')}")
        print(f"  Dimension: {s.get('embeddingDim')}")
        print(f"  Array length: {s.get('embedding_length')}")
    
    return with_embeddings > 0


def test_vector_search():
    """Test vector search functionality"""
    print("\n" + "="*60)
    print("Testing Vector Search")
    print("="*60)
    
    test_query = "What is the nature of consciousness?"
    print(f"\nTest query: '{test_query}'")
    
    # Generate query embedding
    print("\n1. Generating query embedding...")
    query_embedding = generate_query_embedding(test_query)
    if query_embedding:
        print(f"   ✓ Query embedding generated (dim: {len(query_embedding)})")
    else:
        print("   ✗ Failed to generate query embedding")
        return
    
    # Test vector search
    print("\n2. Running vector search...")
    results = vector_search_cosmos(test_query, top_n=5)
    
    print(f"\n3. Results: {len(results)} items found")
    for i, result in enumerate(results[:5], 1):
        score = result.get("vector_score", 0)
        question = result.get("questionText", result.get("question", ""))
        print(f"   {i}. [Score: {score:.4f}] {question[:70]}")


def test_simple_query():
    """Test a simple Cosmos DB query to check VectorDistance function"""
    container = get_cosmos_container()
    
    print("\n" + "="*60)
    print("Testing VectorDistance() Function")
    print("="*60)
    
    # Get a question with embedding
    sample_query = """
    SELECT TOP 1 c.id, c.embedding, c.embeddingModel, c.embeddingDim
    FROM c
    WHERE IS_ARRAY(c.embedding) = true 
       AND ARRAY_LENGTH(c.embedding) = 3072
       AND c.embeddingModel = 'text-embedding-3-large'
    """
    samples = list(container.query_items(
        query=sample_query,
        enable_cross_partition_query=True
    ))
    
    if not samples:
        print("❌ No questions found with matching embeddings")
        return
    
    sample = samples[0]
    test_embedding = sample.get("embedding")
    
    print(f"\nUsing sample embedding from question: {sample.get('id')}")
    print(f"Embedding dimension: {len(test_embedding)}")
    
    # Test VectorDistance function
    # Note: VectorDistance() automatically sorts results (most similar first), so ORDER BY is not allowed
    # Third argument is boolean: true = exact search, false = indexed search
    test_query = """
    SELECT TOP 5
        c.id,
        c.questionText,
        VectorDistance(c.embedding, @testVector, @useExactSearch) AS distance
    FROM c
    WHERE IS_ARRAY(c.embedding) = true
        AND ARRAY_LENGTH(c.embedding) = 3072
        AND c.embeddingModel = 'text-embedding-3-large'
    """
    
    try:
        print("\nTesting VectorDistance() function...")
        results = list(container.query_items(
            query=test_query,
            parameters=[
                {"name": "@testVector", "value": test_embedding},
                {"name": "@useExactSearch", "value": False}  # Use indexed search
            ],
            enable_cross_partition_query=True
        ))
        print(f"✓ VectorDistance() function works! Found {len(results)} results")
        for i, r in enumerate(results[:3], 1):
            print(f"   {i}. Distance: {r.get('distance', 'N/A'):.4f} - {r.get('questionText', 'N/A')[:50]}")
    except Exception as e:
        print(f"❌ VectorDistance() function error: {e}")
        print("   → Vector Search feature may not be enabled or vector index not created")


if __name__ == "__main__":
    print("Vector Search Diagnostic Tool\n")
    
    # Test 1: Check if embeddings exist
    has_embeddings = test_embeddings_exist()
    
    if not has_embeddings:
        print("\n❌ No embeddings found in database!")
        print("   Run: python scripts/add_embeddings_to_questions.py")
        sys.exit(1)
    
    # Test 2: Test VectorDistance function
    test_simple_query()
    
    # Test 3: Test full vector search
    test_vector_search()
    
    print("\n" + "="*60)
    print("Diagnostic Complete")
    print("="*60)
