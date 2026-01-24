"""
Search service for Cosmos DB questions.
Provides three search methods:
1. BM25 (keyword-based) search - uses Azure Cosmos DB Full Text Search
2. Vector (semantic) search - uses Azure Cosmos DB Vector Search
3. Topic/Entity search - uses extracted topics and entities
"""

from typing import List, Dict, Optional
from app.services.cosmos_service import get_cosmos_container
from app.services.question_processor import process_question


# Removed get_all_questions_from_cosmos() - we now use Cosmos DB queries directly
# instead of loading all questions into memory


def bm25_search(query: str, top_n: int = 10) -> List[Dict]:
    """
    BM25 keyword-based search on questions using Azure Cosmos DB's native Full Text Search.
    
    This uses server-side Full Text Search with BM25 scoring - much faster than client-side.
    Requires Full Text Policy to be configured in Cosmos DB.
    
    Args:
        query: Search query text
        top_n: Number of top results to return
    
    Returns:
        List of question documents sorted by BM25 score
    """
    try:
        from app.services.fulltext_search_service import bm25_search_fulltext
        return bm25_search_fulltext(query, top_n)
    except ImportError:
        print("❌ Full Text Search module not found")
        return []
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Full Text Search error: {error_msg}")
        if "FullTextSearch" in error_msg or "fulltext" in error_msg.lower():
            print("   → Full Text Policy may not be configured yet, or indexes are still building")
        return []


def vector_search(query: str, top_n: int = 10, require_video_link: bool = True) -> List[Dict]:
    """
    Vector (semantic) search on questions using embeddings.
    
    Uses Azure Cosmos DB VectorDistance() function if Vector Search is enabled.
    Falls back to empty list if feature is not enabled or embeddings are missing.
    
    Args:
        query: Search query text
        top_n: Number of top results to return
        require_video_link: If True, only return questions WITH video_link (answered questions).
                          If False, only return questions WITHOUT video_link (unanswered questions).
                          Default: True (for main search)
    
    Returns:
        List of question documents sorted by vector similarity
    """
    try:
        # Try using Cosmos DB native vector search
        from app.services.vector_search_service import vector_search_cosmos
        return vector_search_cosmos(query, top_n, require_video_link=require_video_link)
    except ImportError:
        # Fallback: return empty if vector search service not available
        return []
    except Exception as e:
        # If VectorDistance() fails (feature not enabled), return empty
        print(f"Vector search error (may not be enabled yet): {e}")
        return []


def topic_entity_search(query: str, top_n: int = 50, require_video_link: bool = True) -> List[Dict]:
    """
    Search questions by matching topics using Azure Cosmos DB Full-Text Search.
    
    Uses server-side Full-Text Search with BM25 scoring for efficient topic matching.
    Full-Text Search provides:
    - Stemming (e.g., "suffer" matches "suffering")
    - BM25 relevance scoring
    - Server-side processing (no client-side filtering)
    
    First processes the query to extract topics and entities,
    then uses Cosmos DB Full-Text Search functions (FullTextContainsAny, FullTextScore)
    to find and rank matching questions.
    
    Custom scoring multipliers are applied:
    - 3x for questions matching ALL query topics
    - 1.5x for questions matching multiple (but not all) topics
    - Even distribution when all results match only 1 topic
    
    Args:
        query: Search query text
        top_n: Number of top results to return
        require_video_link: If True, only return questions WITH video_link (answered questions).
                          If False, only return questions WITHOUT video_link (unanswered questions).
                          Default: True (for main search)
    
    Returns:
        List of question documents sorted by combined BM25 + custom topic match score
    """
    container = get_cosmos_container()
    
    # Process query to extract topics and entities
    try:
        processed = process_question(query)
        query_topics = [t.lower() for t in processed["topics"]]
        query_entities = processed["entities"]  # List of {type, name} dicts (extracted but not used in query)
    except Exception as e:
        print(f"Error processing query for topic/entity search: {e}")
        return []
    
    # Only search by topics, not entities
    if not query_topics:
        return []
    
    try:
        # Build Cosmos DB query using Full-Text Search for topics
        # Use FullTextContainsAll for matching ALL topics (highest priority)
        # Use FullTextContainsAny for matching ANY topic (fallback)
        # Use FullTextScore with ORDER BY RANK for BM25 scoring
        
        # Escape topic strings for SQL (replace single quotes with double single quotes)
        # Topics are already lowercased and extracted by LLM, so they're safe to use
        escaped_topics = [topic.replace("'", "''") for topic in query_topics]
        
        parameters = []
        
        # Use ARRAY_CONTAINS to filter by topics array (topic-based matching)
        # This ensures we only get questions that have the topics in their topics array
        conditions = []
        parameters = []
        
        # Match topics using ARRAY_CONTAINS (case-insensitive)
        for i, topic in enumerate(query_topics):
            param_name = f"@topic{i}"
            conditions.append(f"ARRAY_CONTAINS(c.topics, {param_name}, true)")
            parameters.append({"name": param_name, "value": topic})
        
        if not conditions:
            return []
        
        # Build WHERE clause - match if any topic matches
        where_clause = " OR ".join(conditions)
        
        # Add video_link filter based on require_video_link parameter
        if require_video_link:
            # Only return questions that HAVE a video_link (answered questions)
            video_link_filter = "AND IS_DEFINED(c.video_link) AND c.video_link != null AND c.video_link != ''"
        else:
            # Only return questions that DON'T have a video_link (unanswered questions in queue)
            video_link_filter = "AND (NOT IS_DEFINED(c.video_link) OR c.video_link = null OR c.video_link = '')"
        
        # Optional: Use Full-Text Search on questionText for BM25 ranking
        # This can help with relevance ranking while still filtering by topics array
        if len(query_topics) == 1:
            topic_str = f"'{escaped_topics[0]}'"
            order_by_clause = f"ORDER BY RANK FullTextScore(c.questionText, {topic_str})"
        elif len(query_topics) > 1:
            topic_strs = [f"'{t}'" for t in escaped_topics]
            order_by_clause = f"ORDER BY RANK FullTextScore(c.questionText, {', '.join(topic_strs)})"
        else:
            order_by_clause = ""
        
        # Query: Filter by topics array, optionally rank by Full-Text Search on questionText
        # Request more items to have enough for our custom topic-based scoring and distribution logic
        # Only select fields we actually use
        query_sql = f"""
        SELECT TOP @top_n
            c.id,
            c.questionText,
            c.domain,
            c.topics,
            c.entities,
            c.video_link,
            c.full_video_link,
            c.playlist_link,
            c.voteUp
        FROM c
        WHERE ({where_clause})
            AND IS_ARRAY(c.topics) = true
            {video_link_filter}
        {order_by_clause}
        """
        
        # Request 2x items to have enough for custom scoring and even distribution
        parameters.append({"name": "@top_n", "value": top_n * 2})
        
        print(f"🔍 Topic/Entity search query (using Full-Text Search): {query_sql}")
        print(f"   Query topics: {query_topics}")
        print(f"   Query entities (extracted but not used in query): {query_entities}")
        print(f"   Using Full-Text Search with BM25 scoring (server-side)")
        print(f"   Requesting {top_n * 2} items from Cosmos DB, will return top {top_n} after custom scoring")
        print(f"   Parameters: {parameters}")
        
        try:
            items = list(container.query_items(
                query=query_sql,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            print(f"✅ Cosmos DB returned {len(items)} items from Full-Text Search query")
        except Exception as query_error:
            error_msg = str(query_error)
            print(f"❌ Error executing Full-Text Search query: {error_msg}")
            print(f"   Query was: {query_sql}")
            print(f"   Parameters were: {parameters}")
            import traceback
            traceback.print_exc()
            # Return empty list - the error will be logged above
            print(f"   ⚠️  Returning empty results due to Full-Text Search error")
            return []
        
        # Hybrid scoring: Combine BM25 ranking (from Full-Text Search) with custom multipliers
        # Items are already sorted by BM25 score (via ORDER BY RANK FullTextScore)
        # We'll use the BM25 ranking as a base, then apply our custom multipliers:
        # - 3x for matching ALL topics
        # - 1.5x for matching multiple topics
        # Full-Text Search handles stemming (e.g., "suffer" matches "suffering") automatically
        
        query_topics_set = set(query_topics)
        
        print(f"   Looking for topics: {query_topics_set}")
        print(f"   (Entities extracted but not used in query or scoring)")
        print(f"   Using Full-Text Search BM25 ranking + custom multipliers")
        
        # Check if we have questions with both topics (for debugging)
        questions_with_both_topics = []
        
        scored_items = []
        for idx, item in enumerate(items):
            # Base score from BM25 ranking (higher position = higher BM25 score)
            # Invert so first item gets highest base score: (len - idx) / len
            # This gives us a 0-1 normalized base score from BM25 ranking
            bm25_base_score = (len(items) - idx) / max(len(items), 1) if items else 0.0
            
            # Match topics - Full-Text Search already handles stemming, but we verify matches
            question_topics = set(t.lower() for t in item.get("topics", []))
            topic_matches = query_topics_set.intersection(question_topics)
            
            # Check for fuzzy matches (fallback for cases Full-Text Search might miss)
            # This handles abbreviations like 'ai' vs 'artificial intelligence'
            fuzzy_matches = set()
            similar_topics_found = []
            if len(query_topics_set) > 1 and len(topic_matches) < len(query_topics_set):
                missing_query_topics = query_topics_set - topic_matches
                for qt in missing_query_topics:
                    for qt_db in question_topics:
                        # Check for substring/abbreviation matches
                        if (qt in qt_db or qt_db in qt or 
                            (len(qt) >= 2 and qt_db.startswith(qt)) or
                            (len(qt_db) >= 2 and qt.startswith(qt_db)) or
                            any(word in qt_db.split() for word in qt.split() if len(word) > 2)):
                            fuzzy_matches.add(qt)
                            similar_topics_found.append((qt, qt_db))
            
            # Log questions with potential topic name mismatches
            if similar_topics_found and len(questions_with_both_topics) < 5:
                questions_with_both_topics.append({
                    'question': item.get('questionText', '')[:60],
                    'db_topics': item.get('topics', []),
                    'query_topics': list(query_topics_set),
                    'matches': list(topic_matches),
                    'similar': similar_topics_found
                })
            
            # Use both exact and fuzzy matches for scoring
            all_matches = topic_matches.union(fuzzy_matches)
            
            if all_matches:
                num_matches = len(all_matches)
                num_query_topics = len(query_topics_set)
                
                # Start with BM25 base score, then apply custom multipliers
                # Base: 2.0 per topic match (exact matches count fully)
                base_score = len(topic_matches) * 2.0
                # Fuzzy matches get 1.5x instead of 2.0 (slightly lower)
                base_score += len(fuzzy_matches) * 1.5
                
                # Combine with BM25 ranking: blend BM25 score with topic match score
                # Weight: 70% topic match score, 30% BM25 ranking
                combined_base = (base_score * 0.7) + (bm25_base_score * 10.0 * 0.3)  # Scale BM25 to similar range
                
                # Priority 1: Questions matching ALL query topics get highest score
                matches_all_topics = num_matches == num_query_topics and num_query_topics > 1
                if matches_all_topics:
                    # Much higher score for matching all topics: combined_base * 3.0
                    combined_base *= 3.0
                    match_type = "exact" if len(fuzzy_matches) == 0 else "fuzzy"
                    print(f"   ⭐ Question matches ALL topics ({match_type}): {item.get('questionText', '')[:60]}... (topics: {item.get('topics', [])}, query: {list(query_topics_set)})")
                # Priority 2: Questions matching multiple (but not all) topics get bonus
                elif num_matches > 1:
                    # Bonus for matching multiple topics
                    combined_base *= 1.5
                
                score = combined_base
                
                # Store match count for secondary sorting
                item["_match_count"] = num_matches
            else:
                # No matches found (shouldn't happen with Full-Text Search, but handle gracefully)
                score = bm25_base_score * 0.1  # Very low score for items that somehow don't match
                item["_match_count"] = 0
            
            if score > 0:
                item["topic_entity_score"] = float(score)
                scored_items.append((score, item))
                # Log first few items for debugging
                if len(scored_items) <= 5:
                    print(f"   📊 Score {score:.1f}: {item.get('questionText', '')[:60]}... (topics: {item.get('topics', [])}, matches: {topic_matches}, BM25 rank: {idx+1})")
        
        # Log questions that might have both topics but didn't match due to naming differences
        if questions_with_both_topics:
            print(f"   ⚠️  Found {len(questions_with_both_topics)} questions with potential topic name mismatches:")
            for q in questions_with_both_topics[:5]:  # Show first 5
                print(f"      - '{q['question']}...'")
                print(f"        DB topics: {q['db_topics']}")
                print(f"        Query topics: {q['query_topics']}")
                print(f"        Matched: {q['matches']}")
                print(f"        Similar (query->db): {q['similar']}")
        
        print(f"   Total scored items: {len(scored_items)}")
        
        # Sort by: 1) match count (descending), 2) score (descending)
        # This ensures questions matching ALL topics rank highest, then multiple, then single
        scored_items.sort(key=lambda x: (x[1].get("_match_count", 0), x[0]), reverse=True)
        
        # If all questions have same match count (e.g., all match 1 topic), evenly distribute
        if scored_items:
            first_match_count = scored_items[0][1].get("_match_count", 0)
            all_same_count = all(item[1].get("_match_count", 0) == first_match_count for item in scored_items)
            
            if all_same_count and first_match_count == 1 and len(query_topics_set) > 1:
                # All match only 1 topic - evenly distribute between query topics
                print(f"   📊 All results match only 1 topic - evenly distributing between {len(query_topics_set)} query topics")
                
                # Group by which topic they match
                topic_groups = {}
                for score, item in scored_items:
                    question_topics = set(t.lower() for t in item.get("topics", []))
                    matched_topic = list(query_topics_set.intersection(question_topics))[0] if query_topics_set.intersection(question_topics) else None
                    if matched_topic:
                        if matched_topic not in topic_groups:
                            topic_groups[matched_topic] = []
                        topic_groups[matched_topic].append((score, item))
                
                # Interleave results from each topic group
                distributed = []
                max_per_topic = top_n // len(query_topics_set)
                remainder = top_n % len(query_topics_set)
                
                for i in range(max_per_topic + (1 if remainder > 0 else 0)):
                    for topic in query_topics_set:
                        if topic in topic_groups and len(topic_groups[topic]) > i:
                            distributed.append(topic_groups[topic][i])
                        if len(distributed) >= top_n:
                            break
                    if len(distributed) >= top_n:
                        break
                
                results = [item for score, item in distributed[:top_n]]
            else:
                # Normal sorting by match count then score
                results = [item for score, item in scored_items][:top_n]
        else:
            results = []
        
        # Clean up temporary fields
        for item in results:
            item.pop("_match_count", None)
        print(f"✅ Returning top {len(results)} results (scores: {[f'{s:.1f}' for s, _ in scored_items[:len(results)]]})")
        
        return results
    
    except Exception as e:
        print(f"Error in topic/entity search: {e}")
        import traceback
        traceback.print_exc()
        return []


def search_all_methods(query: str, top_n: int = 10) -> Dict[str, List[Dict]]:
    """
    Run search methods and return results.
    
    Args:
        query: Search query text
        top_n: Number of top results per method
    
    Returns:
        Dictionary with two arrays:
        - "vector_results": Vector search results
        - "topic_entity_results": Topic/entity search results
    """
    return {
        "vector_results": vector_search(query, top_n),
        "topic_entity_results": topic_entity_search(query, top_n)
    }
