#!/usr/bin/env python3
"""Simple script to add embeddings to all questions in Cosmos DB."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.cosmos_service import get_cosmos_container
from app.services.llm_service import get_openai_client

def main():
    container = get_cosmos_container()
    openai_client = get_openai_client()
    
    print("Fetching questions...")
    query = "SELECT c.id, c.questionText FROM c WHERE IS_ARRAY(c.embedding) = false OR c.embedding = null"
    questions = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    print(f"Found {len(questions)} questions without embeddings\n")
    
    success = 0
    errors = 0
    
    for i, q in enumerate(questions, 1):
        question_text = q.get("questionText", "")
        question_id = q.get("id")
        
        if i % 10 == 0 or i == 1:
            print(f"[{i}/{len(questions)}] {question_text[:60]}...")
        
        try:
            # Generate embedding
            response = openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=question_text
            )
            
            embedding = response.data[0].embedding
            
            # Update question
            item = container.read_item(item=question_id, partition_key=question_id)
            item["embedding"] = embedding
            item["embeddingModel"] = "text-embedding-3-large"
            item["embeddingDim"] = len(embedding)
            
            container.replace_item(item=question_id, body=item, partition_key=question_id)
            success += 1
            
        except Exception as e:
            errors += 1
            print(f"  ✗ Error: {e}")
    
    print(f"\n✅ Done!")
    print(f"   Success: {success}")
    print(f"   Errors: {errors}")

if __name__ == "__main__":
    main()
