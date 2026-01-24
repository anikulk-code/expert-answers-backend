"""
Vector search service using Azure Cosmos DB VectorDistance() function.

This service implements vector similarity search using Cosmos DB's native
vector search capabilities after Vector Search feature is enabled.
"""

import os
from typing import List, Dict, Optional
from app.services.cosmos_service import get_cosmos_container
from app.services.llm_service import get_openai_client


def generate_query_embedding(query: str, model: str = "text-embedding-3-large") -> Optional[List[float]]:
    """
    Generate embedding for a search query.
    
    Uses the full query text (not canonical_text) for better semantic matching.
    This matches how stored embeddings are generated (from full questionText).
    
    Args:
        query: Search query text (raw user query)
        model: Embedding model to use (must match stored embeddings)
    
    Returns:
        Embedding vector or None if error
    """
    try:
        openai_client = get_openai_client()
        
        # Use full query text for better semantic understanding
        # This matches how stored embeddings are generated (from questionText, not canonical_text)
        print(f"   📝 Generating embedding for query: '{query}'")
        response = openai_client.embeddings.create(
            model=model,
            input=query
        )
        
        embedding = response.data[0].embedding
        print(f"   ✅ Generated embedding: length={len(embedding)}, first 3 values={embedding[:3] if len(embedding) >= 3 else embedding}")
        return embedding
    except Exception as e:
        print(f"Error generating query embedding: {e}")
        return None


def vector_search_cosmos(
    query: str,
    top_n: int = 10,
    embedding_model: str = "text-embedding-3-large",
    embedding_dim: int = 3072,
    require_video_link: bool = True
) -> List[Dict]:
    """
    Vector search using Cosmos DB VectorDistance() function.
    
    This uses Azure Cosmos DB's native vector search after Vector Search
    feature is enabled and vector index is created.
    
    Args:
        query: Search query text
        top_n: Number of top results to return
        embedding_model: Model used for embeddings (must match stored)
        embedding_dim: Dimension of embedding vectors
        require_video_link: If True, only return questions WITH video_link (answered questions).
                          If False, only return questions WITHOUT video_link (unanswered questions).
                          Default: True (for main search)
    
    Returns:
        List of question documents sorted by vector similarity
    """
    container = get_cosmos_container()
    
    # Log the actual query being used
    print(f"🔍 Vector search called with query: '{query}'")
    
    # Generate embedding for query
    query_embedding = generate_query_embedding(query, embedding_model)
    if not query_embedding:
        print(f"❌ Failed to generate embedding for query: '{query}'")
        return []
    
    # Log first few values of embedding to verify it's different for different queries
    embedding_preview = query_embedding[:5] if len(query_embedding) >= 5 else query_embedding
    print(f"   Generated embedding preview (first 5 values): {embedding_preview}")
    print(f"   🔍 CRITICAL: Query='{query}', Embedding hash (first 10 values): {query_embedding[:10]}")
    
    # Validate embedding dimension
    if len(query_embedding) != embedding_dim:
        print(f"Warning: Query embedding dimension ({len(query_embedding)}) doesn't match expected ({embedding_dim})")
        return []
    
    try:
        # First, check if any embeddings exist
        check_query = "SELECT VALUE COUNT(1) FROM c WHERE IS_ARRAY(c.embedding) = true AND ARRAY_LENGTH(c.embedding) > 0"
        try:
            embedding_count = list(container.query_items(
                query=check_query,
                enable_cross_partition_query=True
            ))[0]
            print(f"🔍 Found {embedding_count} questions with embeddings")
            if embedding_count == 0:
                print("⚠️  No embeddings found in database. Vector search requires embeddings to be generated first.")
                return []
        except Exception as e:
            print(f"⚠️  Could not count embeddings: {e}")
        
        # Use VectorDistance() function for vector search
        # VectorDistance(embedding, @queryVector, 'cosine') returns distance
        # Lower distance = more similar, so we order by distance ASC
        print(f"🔍 Running vector search query...")
        print(f"   Query embedding dimension: {len(query_embedding)}")
        print(f"   Expected dimension: {embedding_dim}")
        print(f"   Embedding model: {embedding_model}")
        
        # Add video_link filter based on require_video_link parameter
        if require_video_link:
            # Only return questions that HAVE a video_link (answered questions)
            video_link_filter = "AND IS_DEFINED(c.video_link) AND c.video_link != null AND c.video_link != ''"
        else:
            # Only return questions that DON'T have a video_link (unanswered questions in queue)
            video_link_filter = "AND (NOT IS_DEFINED(c.video_link) OR c.video_link = null OR c.video_link = '')"
        
        # Use VectorDistance() function for vector search
        # According to Azure docs: VectorDistance(embedding, queryVector, useExactSearch)
        # - useExactSearch: true = exact search (brute force), false = indexed search
        # - Results must be ordered by VectorDistance() to get similarity ranking
        # - Can't use c.* with VectorDistance(), must select specific fields
        # IMPORTANT: Use parameterized query to ensure Cosmos DB uses the correct vector for each query
        query_sql = f"""
        SELECT TOP @top_n
            c.id,
            c.questionText,
            c.normalizedText,
            c.canonical_text,
            c.domain,
            c.topics,
            c.entities,
            c.tags,
            c.video_link,
            c.full_video_link,
            c.playlist_link,
            c.voteUp,
            c.timesAsked,
            c.status,
            c.createdAt,
            c.updatedAt,
            c.embedding,
            c.embeddingModel,
            c.embeddingDim,
            VectorDistance(c.embedding, @queryVector, @useExactSearch) AS vector_distance
        FROM c
        WHERE IS_ARRAY(c.embedding) = true
            AND ARRAY_LENGTH(c.embedding) = @embedding_dim
            {video_link_filter}
        ORDER BY VectorDistance(c.embedding, @queryVector, @useExactSearch)
        """
        
        # Note: We're not filtering by embeddingModel in the WHERE clause
        # to avoid potential issues. We'll filter in Python if needed.
        
        # Convert embedding to list (ensure it's a Python list, not numpy array or other type)
        query_vector_list = list(query_embedding) if not isinstance(query_embedding, list) else query_embedding
        
        parameters = [
            {"name": "@queryVector", "value": query_vector_list},  # Pass as list directly
            {"name": "@top_n", "value": top_n},
            {"name": "@embedding_dim", "value": embedding_dim},
            {"name": "@embedding_model", "value": embedding_model},
            {"name": "@useExactSearch", "value": False}  # Use indexed search (faster). Set to True for exact brute-force search
        ]
        
        print(f"   ✅ Using PARAMETERIZED vector - embedding length: {len(query_vector_list)}")
        print(f"   First 3 values of parameterized vector: {query_vector_list[:3]}")
        print(f"   Vector type: {type(query_vector_list)}, first element type: {type(query_vector_list[0]) if len(query_vector_list) > 0 else 'N/A'}")
        
        print(f"   Executing vector search SQL query...")
        print(f"   Query SQL: {query_sql}")
        print(f"   Parameters count: {len(parameters)}")
        # Log parameter names and types (but not full vector values)
        for param in parameters:
            if param['name'] == '@queryVector':
                vec_val = param['value']
                print(f"   Parameter @queryVector: type={type(vec_val)}, length={len(vec_val) if hasattr(vec_val, '__len__') else 'N/A'}, first 3 values={vec_val[:3] if hasattr(vec_val, '__len__') and len(vec_val) >= 3 else 'N/A'}")
            else:
                print(f"   Parameter {param['name']}: {param['value']} (type: {type(param['value'])})")
        try:
            items = list(container.query_items(
                query=query_sql,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            print(f"✅ Vector search query returned {len(items)} results")
            if len(items) > 0:
                print(f"   First result ID: {items[0].get('id', 'N/A')}")
                print(f"   First result question: {items[0].get('questionText', 'N/A')[:60]}...")
                print(f"   First result vector_distance: {items[0].get('vector_distance', 'N/A')}")
                print(f"   First result topics: {items[0].get('topics', [])}")
                # Log first 3 result IDs to check if they're all the same
                if len(items) >= 3:
                    print(f"   First 3 result IDs: {[item.get('id', 'N/A')[:8] + '...' for item in items[:3]]}")
                    print(f"   First 3 distances: {[item.get('vector_distance', 'N/A') for item in items[:3]]}")
                    print(f"   First 3 questions: {[item.get('questionText', 'N/A')[:50] + '...' for item in items[:3]]}")
                # Verify the query vector is actually being used by checking if distances differ
                distances = [item.get('vector_distance') for item in items if item.get('vector_distance') is not None]
                if len(distances) > 1:
                    print(f"   Distance range: min={min(distances):.4f}, max={max(distances):.4f}, unique_count={len(set(distances))}")
                # CRITICAL: Log a sample of stored embeddings to verify they're different
                if len(items) >= 2:
                    emb1 = items[0].get('embedding', [])
                    emb2 = items[1].get('embedding', [])
                    if emb1 and emb2 and len(emb1) >= 3 and len(emb2) >= 3:
                        print(f"   🔍 Stored embedding check:")
                        print(f"      Result #1 embedding (first 3): {emb1[:3]}")
                        print(f"      Result #2 embedding (first 3): {emb2[:3]}")
                        print(f"      Are embeddings different? {emb1[:3] != emb2[:3]}")
        except Exception as query_error:
            error_msg = str(query_error)
            error_type = type(query_error).__name__
            print(f"❌ Vector search query error:")
            print(f"   Error type: {error_type}")
            print(f"   Error message: {error_msg}")
            import traceback
            traceback.print_exc()
            raise  # Re-raise the error
        
        # Convert distance to similarity score (1 - distance for cosine)
        # Cosine distance ranges from 0 (identical) to 2 (opposite)
        # Similarity = 1 - distance (ranges from -1 to 1, but typically 0 to 1)
        results = []
        print(f"   Converting {len(items)} results from distance to similarity score...")
        for i, item in enumerate(items):
            distance = item.get("vector_distance", 2.0)
            similarity = 1.0 - distance  # Convert distance to similarity
            item["vector_score"] = float(similarity)
            
            # Log first 3 results for debugging
            if i < 3:
                print(f"   Result #{i+1}: distance={distance:.4f}, similarity={similarity:.4f}, question={item.get('questionText', 'N/A')[:50]}...")
            
            # Remove the temporary vector_distance field
            if "vector_distance" in item:
                del item["vector_distance"]
            results.append(item)
        
        print(f"✅ Returning {len(results)} results with scores")
        return results
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error in vector search: {error_msg}")
        # If VectorDistance() is not available (feature not enabled yet),
        # fall back to empty results
        if "VectorDistance" in error_msg or "vector" in error_msg.lower():
            print("   → Vector Search feature may not be enabled yet, or vector index not created")
            print("   → Check Azure Portal: Features > Vector Search for NoSQL API")
            print("   → Vector indexes can only be applied to NEW containers")
        else:
            import traceback
            traceback.print_exc()
        return []
