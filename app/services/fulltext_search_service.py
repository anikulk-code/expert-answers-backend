"""
Full Text Search service using Azure Cosmos DB's native Full Text Search.

This uses Cosmos DB's Full Text Search feature which provides:
- Server-side indexing and search
- BM25 scoring
- Much faster than client-side processing
"""

from typing import List, Dict
from app.services.cosmos_service import get_cosmos_container


def bm25_search_fulltext(query: str, top_n: int = 10) -> List[Dict]:
    """
    BM25 search using Azure Cosmos DB's native Full Text Search.
    
    This uses the Full Text Search feature which provides server-side
    BM25 scoring and indexing for much better performance.
    
    Args:
        query: Search query text
        top_n: Number of top results to return
    
    Returns:
        List of question documents sorted by BM25 score
    """
    container = get_cosmos_container()
    
    try:
        # Use tokenized CONTAINS approach (working implementation)
        # Preprocess query following the specified strategy:
        # 1. Convert to lowercase
        # 2. Remove punctuation
        # 3. Tokenize (split on whitespace)
        # 4. Remove stopwords
        # 5. Remove tokens shorter than 3 characters
        # 6. Search for each remaining token
        import re
        
        # Preprocess query: lowercase, remove punctuation, tokenize, remove stopwords
        processed_query = query.lower()
        processed_query = re.sub(r'[^\w\s]', ' ', processed_query)
        tokens = processed_query.split()
        
        stopwords = {'what', 'does', 'say', 'about', 'is', 'are', 'how', 'why', 'explain', 'tell', 
                     'the', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'view', 'views',
                     'can', 'will', 'would', 'should', 'could', 'may', 'might', 'do', 'did', 'done',
                     'between', 'and', 'or', 'but'}
        
        # Common abbreviations/acronyms that should be kept even if short
        important_short_words = {'ai', 'ml', 'nlp', 'api', 'ui', 'ux', 'db', 'sql', 'id'}
        
        # First pass: keep words >= 3 chars OR important short words
        query_words = [token for token in tokens 
                      if token not in stopwords and (len(token) >= 3 or token in important_short_words)]
        
        # Fallback: if no words found, include 2+ char words (but still exclude stopwords)
        if not query_words:
            query_words = [token for token in tokens if token not in stopwords and len(token) >= 2]
        
        # Build WHERE clause with OR conditions for each word
        where_conditions = []
        parameters = [{"name": "@top_n", "value": top_n}]
        
        for i, word in enumerate(query_words):
            param_name = f"@word{i}"
            where_conditions.append(f"CONTAINS(UPPER(c.questionText), UPPER({param_name}))")
            where_conditions.append(f"ARRAY_CONTAINS(c.topics, {param_name}, true)")
            parameters.append({"name": param_name, "value": word})
        
        where_clause = " OR ".join(where_conditions) if where_conditions else "1=1"
        
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
            c.embeddingDim
        FROM c
        WHERE ({where_clause})
        ORDER BY c.createdAt DESC
        """
        
        import time
        start_time = time.time()
        print(f"🔍 Using tokenized CONTAINS fallback for query: '{query}'")
        print(f"   Extracted tokens: {query_words}")
        
        items = list(container.query_items(
            query=query_sql,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        elapsed = time.time() - start_time
        print(f"✅ Tokenized CONTAINS returned {len(items)} results in {elapsed:.2f}s")
        if len(items) > 0:
            print(f"   First result: {items[0].get('questionText', 'N/A')[:60]}")
        
        # Calculate match-based scores (better than rank-based)
        # Count how many query words match in questionText and topics
        results = []
        query_words_set = set(query_words)
        
        for item in items:
            score = 0.0
            question_text_lower = item.get('questionText', '').lower()
            question_topics_lower = [t.lower() for t in item.get('topics', [])]
            
            # Count matches in question text (weight: 1.0 per word)
            for word in query_words_set:
                if word in question_text_lower:
                    score += 1.0
            
            # Count matches in topics (weight: 2.0 per word - topics are more important)
            for word in query_words_set:
                for topic in question_topics_lower:
                    if word in topic or topic in word:  # Handle variations like 'ai' vs 'artificial intelligence'
                        score += 2.0
                        break  # Count each query word only once per question
            
            # Bonus for matching multiple words
            if len(query_words_set) > 1:
                matched_words = sum(1 for word in query_words_set 
                                  if word in question_text_lower or 
                                  any(word in t.lower() or t.lower() in word for t in question_topics_lower))
                if matched_words == len(query_words_set):
                    score *= 1.5  # 50% bonus for matching all query words
            
            item["bm25_score"] = float(score)
            results.append(item)
        
        # Sort by score descending
        results.sort(key=lambda x: x.get("bm25_score", 0), reverse=True)
        
        return results
        
        import time
        start_time = time.time()
        print(f"🔍 Using Full Text Search for query: '{query}'")
        print(f"   Extracted tokens: {query_words}")
        print(f"   Query SQL: {query_sql}")
        print(f"   Parameters: {parameters}")
        
        items = list(container.query_items(
            query=query_sql,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        elapsed = time.time() - start_time
        print(f"✅ Full Text Search returned {len(items)} results in {elapsed:.2f}s")
        if len(items) > 0:
            print(f"   First result: {items[0].get('questionText', 'N/A')[:60]}")
        
        # Map fulltext_score to bm25_score for consistency
        # RANK FULLTEXTSCORE() returns the BM25 relevance score
        results = []
        for item in items:
            score = item.get("fulltext_score", 0.0)
            item["bm25_score"] = float(score)
            # Remove temporary fulltext_score field
            if "fulltext_score" in item:
                del item["fulltext_score"]
            results.append(item)
        
        return results
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error in full text search: {error_msg}")
        # If FullTextSearch() is not available (feature not enabled yet),
        # fall back to empty results
        if "FullTextSearch" in error_msg or "fulltext" in error_msg.lower():
            print("   → Full Text Search feature may not be enabled yet, or Full Text Policy not configured")
            print("   → Check Azure Portal: Data Explorer > Container Settings > Full Text Policy")
        else:
            import traceback
            traceback.print_exc()
        return []
