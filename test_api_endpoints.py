#!/usr/bin/env python3
"""
Test the API endpoints for questions and voting.
Run this while your FastAPI server is running.
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000/api"

def test_health():
    """Test if server is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_add_question():
    """Test adding a question to the queue"""
    print("\n" + "="*50)
    print("Test 1: Add Question to Queue")
    print("="*50)
    
    question = "What does Vedanta say about evolution?"
    payload = {"question": question}
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/questions/queue",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Question added successfully!")
            print(f"   Question: {data.get('question')}")
            print(f"   Upvotes: {data.get('upvotes')}")
            print(f"   ID: {data.get('id')}")
            return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_upvote_question(question):
    """Test upvoting a question"""
    print("\n" + "="*50)
    print("Test 2: Upvote Question")
    print("="*50)
    
    payload = {"question": question}
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/questions/upvote",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Question upvoted successfully!")
            print(f"   Question: {data.get('question')}")
            print(f"   Upvotes: {data.get('upvotes')}")
            return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_get_questions():
    """Test getting all questions"""
    print("\n" + "="*50)
    print("Test 3: Get All Questions")
    print("="*50)
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/questions/queue?limit=10",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            questions = data.get('questions', [])
            print(f"✅ Retrieved {len(questions)} questions")
            
            if questions:
                print("\n   Top questions:")
                for i, q in enumerate(questions[:5], 1):
                    print(f"   {i}. {q.get('question')} ({q.get('upvotes')} upvotes)")
            else:
                print("   No questions in queue yet")
            
            return questions
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_search_with_queue():
    """Test the search endpoint to see queue integration"""
    print("\n" + "="*50)
    print("Test 4: Search Question (with Queue Integration)")
    print("="*50)
    
    question = "What does Vedanta say about evolution?"
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/answers/v1",
            params={"question": question},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Search completed")
            print(f"   Status: {data.get('searchStatus')}")
            print(f"   Stage: {data.get('searchStage')}")
            
            if data.get('queueInfo'):
                queue_info = data['queueInfo']
                print(f"\n   Queue Info:")
                print(f"   - In Queue: {queue_info.get('questionInQueue')}")
                print(f"   - Upvotes: {queue_info.get('upvotes')}")
                
                similar = queue_info.get('similarQuestions', [])
                if similar:
                    print(f"   - Similar Questions: {len(similar)}")
                    for sq in similar[:3]:
                        print(f"     • {sq.get('question')} ({sq.get('upvotes')} upvotes)")
            
            return data
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    print("="*50)
    print("API Endpoint Testing")
    print("="*50)
    
    # Test 0: Check if server is running
    if not test_health():
        print("\n💡 Start your server with: uvicorn app.main:app --reload")
        return
    
    # Test 1: Add question
    question_data = test_add_question()
    if not question_data:
        print("\n❌ Failed to add question. Check your Cosmos DB configuration.")
        return
    
    time.sleep(1)  # Small delay
    
    # Test 2: Upvote question
    test_question = question_data.get('question')
    upvote_data = test_upvote_question(test_question)
    
    time.sleep(1)  # Small delay
    
    # Test 3: Get all questions
    test_get_questions()
    
    time.sleep(1)  # small delay
    
    # Test 4: Test search with queue integration
    test_search_with_queue()
    
    print("\n" + "="*50)
    print("✅ All API tests completed!")
    print("="*50)
    print("\n💡 Your API is ready to integrate with your app!")
    print("   Endpoints:")
    print("   - POST /api/questions/queue - Add question")
    print("   - POST /api/questions/upvote - Upvote question")
    print("   - GET  /api/questions/queue - Get all questions")
    print("   - GET  /api/answers/v1?question=... - Search with queue integration")

if __name__ == "__main__":
    main()

