#!/usr/bin/env python3
"""
Test script for the search comparison API endpoint.
"""

import requests
import json
import sys

API_BASE_URL = "http://localhost:8000/api"

def test_search_comparison(query: str, top_n: int = 10):
    """Test the search comparison endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing Search Comparison API")
    print(f"{'='*60}")
    print(f"Query: '{query}'")
    print(f"Top N: {top_n}\n")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/search/compare",
            params={"query": query, "top_n": top_n},
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        data = response.json()
        
        print(f"Total questions in DB: {data.get('total_questions_in_db', 0)}\n")
        
        # BM25 Results
        bm25_results = data.get("bm25_results", [])
        print(f"📊 BM25 Results ({len(bm25_results)}):")
        print("-" * 60)
        for i, result in enumerate(bm25_results[:5], 1):
            score = result.get("score", 0)
            question = result.get("questionText", "")
            topics = result.get("topics", [])
            print(f"{i}. [{score:.3f}] {question[:70]}")
            if topics:
                print(f"   Topics: {', '.join(topics[:3])}")
        if len(bm25_results) > 5:
            print(f"   ... and {len(bm25_results) - 5} more")
        print()
        
        # Vector Results
        vector_results = data.get("vector_results", [])
        print(f"🔍 Vector Results ({len(vector_results)}):")
        print("-" * 60)
        if vector_results:
            for i, result in enumerate(vector_results[:5], 1):
                score = result.get("score", 0)
                question = result.get("questionText", "")
                print(f"{i}. [{score:.3f}] {question[:70]}")
            if len(vector_results) > 5:
                print(f"   ... and {len(vector_results) - 5} more")
        else:
            print("   (No embeddings available yet - vector search requires embeddings)")
        print()
        
        # Topic/Entity Results
        topic_results = data.get("topic_entity_results", [])
        print(f"🏷️  Topic/Entity Results ({len(topic_results)}):")
        print("-" * 60)
        for i, result in enumerate(topic_results[:5], 1):
            score = result.get("score", 0)
            question = result.get("questionText", "")
            topics = result.get("topics", [])
            entities = result.get("entities", [])
            print(f"{i}. [{score:.1f}] {question[:70]}")
            if topics:
                print(f"   Topics: {', '.join(topics[:3])}")
            if entities:
                entity_str = ", ".join([e.get("name", "") for e in entities[:2]])
                print(f"   Entities: {entity_str}")
        if len(topic_results) > 5:
            print(f"   ... and {len(topic_results) - 5} more")
        print()
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on port 8000")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "What is the vedantic view of evolution?"
    
    test_search_comparison(query, top_n=10)
