"""
Vector search service using Azure Cosmos DB VectorDistance() function.

This service implements vector similarity search using Cosmos DB's native
vector search capabilities after Vector Search feature is enabled.
"""

import os
from typing import List, Dict, Optional
from app.services.cosmos_service import get_cosmos_container
from app.services.llm_service import get_openai_client

_DEBUG_SEARCH = os.getenv("DEBUG_SEARCH", "").lower() in ("1", "true", "yes")


def _debug(*args, **kwargs):
    if _DEBUG_SEARCH:
        print(*args, **kwargs)


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
        _debug(f"   Generating embedding for query: '{query}'")
        response = openai_client.embeddings.create(
            model=model,
            input=query
        )
        embedding = response.data[0].embedding
        _debug(
            f"   Generated embedding: length={len(embedding)}, "
            f"first 3 values={embedding[:3] if len(embedding) >= 3 else embedding}"
        )
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
    _debug(f"Vector search called with query: '{query}'")

    query_embedding = generate_query_embedding(query, embedding_model)
    if not query_embedding:
        print(f"Failed to generate embedding for query: '{query}'")
        return []

    if len(query_embedding) != embedding_dim:
        print(
            f"Warning: Query embedding dimension ({len(query_embedding)}) "
            f"doesn't match expected ({embedding_dim})"
        )
        return []

    try:
        if require_video_link:
            video_link_filter = (
                "AND IS_DEFINED(c.video_link) AND c.video_link != null AND c.video_link != ''"
            )
        else:
            video_link_filter = (
                "AND (NOT IS_DEFINED(c.video_link) OR c.video_link = null OR c.video_link = '')"
            )

        # Select only fields needed downstream. Never return c.embedding
        # (3072 floats × top_n) — it is unused except for debug and dominates payload size.
        query_sql = f"""
        SELECT TOP @top_n
            c.id,
            c.questionText,
            c.domain,
            c.topics,
            c.entities,
            c.video_link,
            c.voteUp,
            c.votes,
            c.upvotes,
            VectorDistance(c.embedding, @queryVector, @useExactSearch) AS vector_distance
        FROM c
        WHERE IS_ARRAY(c.embedding) = true
            AND ARRAY_LENGTH(c.embedding) = @embedding_dim
            {video_link_filter}
        ORDER BY VectorDistance(c.embedding, @queryVector, @useExactSearch)
        """

        query_vector_list = (
            list(query_embedding) if not isinstance(query_embedding, list) else query_embedding
        )

        parameters = [
            {"name": "@queryVector", "value": query_vector_list},
            {"name": "@top_n", "value": top_n},
            {"name": "@embedding_dim", "value": embedding_dim},
            {"name": "@embedding_model", "value": embedding_model},
            {"name": "@useExactSearch", "value": False},
        ]

        _debug(f"Executing vector search (top_n={top_n}, dim={embedding_dim})")
        items = list(container.query_items(
            query=query_sql,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        _debug(f"Vector search returned {len(items)} results")

        results = []
        for item in items:
            distance = item.get("vector_distance", 2.0)
            item["vector_score"] = float(1.0 - distance)
            if "vector_distance" in item:
                del item["vector_distance"]
            results.append(item)

        return results

    except Exception as e:
        error_msg = str(e)
        print(f"Error in vector search: {error_msg}")
        if "VectorDistance" in error_msg or "vector" in error_msg.lower():
            print("   Vector Search feature may not be enabled yet, or vector index not created")
        else:
            import traceback
            traceback.print_exc()
        return []
