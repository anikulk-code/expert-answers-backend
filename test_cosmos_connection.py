#!/usr/bin/env python3
"""
Quick test script to verify Azure Cosmos DB connection.
Run this after setting up your .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

def test_cosmos_connection():
    """Test the Cosmos DB connection"""
    print("Testing Azure Cosmos DB connection...")
    print("-" * 50)
    
    # Check environment variables
    endpoint = os.getenv('AZURE_COSMOS_ENDPOINT')
    key = os.getenv('AZURE_COSMOS_KEY')
    database_name = os.getenv('AZURE_COSMOS_DATABASE_NAME', 'expert-answers-db')
    container_name = os.getenv('AZURE_COSMOS_CONTAINER_NAME', 'questions')
    
    if not endpoint:
        print("❌ ERROR: AZURE_COSMOS_ENDPOINT not found in .env file")
        return False
    
    if not key:
        print("❌ ERROR: AZURE_COSMOS_KEY not found in .env file")
        return False
    
    print(f"✓ Endpoint: {endpoint}")
    print(f"✓ Database: {database_name}")
    print(f"✓ Container: {container_name}")
    print()
    
    try:
        from app.services.cosmos_service import (
            get_cosmos_client,
            get_cosmos_database,
            get_cosmos_container,
            add_question_to_queue,
            get_questions_queue
        )
        
        print("Testing connection...")
        client = get_cosmos_client()
        database = get_cosmos_database()
        container = get_cosmos_container()
        
        print("✓ Successfully connected to Cosmos DB!")
        print()
        
        # Test adding a question
        print("Testing add question...")
        test_question = "Test question - please delete me"
        result = add_question_to_queue(test_question)
        print(f"✓ Question added: {result.get('question')}")
        print(f"  ID: {result.get('id')}")
        print(f"  Upvotes: {result.get('upvotes')}")
        print()
        
        # Test getting questions
        print("Testing get questions...")
        questions = get_questions_queue(limit=5)
        print(f"✓ Retrieved {len(questions)} questions from queue")
        if questions:
            print("  Sample questions:")
            for q in questions[:3]:
                print(f"    - {q.get('question')} ({q.get('upvotes')} upvotes)")
        print()
        
        print("=" * 50)
        print("✅ All tests passed! Cosmos DB is working correctly.")
        print("=" * 50)
        
        return True
        
    except ImportError as e:
        print(f"❌ ERROR: Could not import cosmos_service: {e}")
        print("   Make sure you've installed dependencies: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        print()
        print("Common issues:")
        print("  1. Check your AZURE_COSMOS_ENDPOINT (should end with :443/)")
        print("  2. Check your AZURE_COSMOS_KEY (should be the PRIMARY KEY)")
        print("  3. Make sure your Cosmos DB account is active in Azure Portal")
        print("  4. Check if your IP is allowed (if firewall rules are enabled)")
        return False

if __name__ == "__main__":
    success = test_cosmos_connection()
    exit(0 if success else 1)

