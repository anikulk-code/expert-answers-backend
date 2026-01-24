import os
from typing import List, Dict, Optional
from datetime import datetime
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from dotenv import load_dotenv
import uuid
from app.services.question_processor import process_question

load_dotenv()

# Cosmos DB configuration
COSMOS_ENDPOINT = os.getenv('AZURE_COSMOS_ENDPOINT')
COSMOS_KEY = os.getenv('AZURE_COSMOS_KEY')
COSMOS_DATABASE_NAME = os.getenv('AZURE_COSMOS_DATABASE_NAME', 'expert-answers-db')
COSMOS_CONTAINER_NAME = os.getenv('AZURE_COSMOS_CONTAINER_NAME', 'questions')

# Global client and container
_cosmos_client = None
_cosmos_database = None
_cosmos_container = None

def get_cosmos_client():
    """Initialize and return Cosmos DB client"""
    global _cosmos_client
    if _cosmos_client is None:
        if not COSMOS_ENDPOINT or not COSMOS_KEY:
            raise ValueError("AZURE_COSMOS_ENDPOINT and AZURE_COSMOS_KEY must be set in environment variables")
        _cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    return _cosmos_client

def get_cosmos_database():
    """Get or create the Cosmos DB database"""
    global _cosmos_database
    if _cosmos_database is None:
        client = get_cosmos_client()
        try:
            _cosmos_database = client.create_database_if_not_exists(id=COSMOS_DATABASE_NAME)
        except exceptions.CosmosAccessConditionFailedError:
            _cosmos_database = client.get_database_client(COSMOS_DATABASE_NAME)
    return _cosmos_database

def get_cosmos_container():
    """Get or create the Cosmos DB container for questions"""
    global _cosmos_container
    if _cosmos_container is None:
        database = get_cosmos_database()
        try:
            # Check if vector search is enabled (via environment variable)
            # If enabled, we'll add vector index policy
            # Note: Vector indexes can only be applied to NEW containers
            # For existing containers, use setup_vector_index.py script
            
            indexing_policy = None
            vector_search_enabled = os.getenv("COSMOS_VECTOR_SEARCH_ENABLED", "false").lower() == "true"
            
            if vector_search_enabled:
                # Vector index policy for text-embedding-3-large (3072 dimensions)
                indexing_policy = {
                    "indexingMode": "consistent",
                    "automatic": True,
                    "includedPaths": [{"path": "/*"}],
                    "excludedPaths": [{"path": "/\"_etag\"/?"}],
                    "vectorIndexes": [
                        {
                            "path": "/embedding",
                            "type": "flat"  # flat, quantizedFlat, or DiskANN
                        }
                    ]
                }
            
            # For serverless accounts, don't specify offer_throughput
            if indexing_policy:
                _cosmos_container = database.create_container_if_not_exists(
                    id=COSMOS_CONTAINER_NAME,
                    partition_key=PartitionKey(path="/id"),
                    indexing_policy=indexing_policy
                )
            else:
                _cosmos_container = database.create_container_if_not_exists(
                    id=COSMOS_CONTAINER_NAME,
                    partition_key=PartitionKey(path="/id")
                )
        except exceptions.CosmosAccessConditionFailedError:
            _cosmos_container = database.get_container_client(COSMOS_CONTAINER_NAME)
    return _cosmos_container

def normalize_question(question: str) -> str:
    """Normalize question for comparison (lowercase, strip)"""
    return question.strip().lower()

def add_question_to_queue(
    question: str,
    domain: Optional[str] = None,
    video_link: Optional[str] = None,
    full_video_link: Optional[str] = None,
    playlist_link: Optional[str] = None,
    tags: Optional[List[str]] = None,
    embedding: Optional[List[float]] = None,
    embedding_model: Optional[str] = None,
    embedding_dim: Optional[int] = None
) -> Dict:
    """
    Add a question to the queue in Cosmos DB with the new schema.
    
    Args:
        question: Question text
        video_link: Link to video segment (with timestamp if available)
        full_video_link: Link to full video (if available)
        playlist_link: Link to playlist (if available)
    
    Returns:
        The created question document
    """
    container = get_cosmos_container()
    question_normalized = normalize_question(question)
    
    # Check if question already exists
    existing = find_question_by_text(question)
    if existing:
        return existing
    
    # Process question to compute canonical text, topics, and entities
    try:
        processed = process_question(question)
        canonical_text = processed["canonical_text"]
        topics = processed["topics"]
        entities = processed["entities"]
    except Exception as e:
        print(f"Error processing question: {e}")
        # Fallback values
        canonical_text = question.lower()
        topics = []
        entities = []
    
    # Create new question document with new schema (aligned with reference schema)
    question_id = str(uuid.uuid4())
    question_doc = {
        "id": question_id,
        "domain": domain or "philosophy",  # Default to philosophy for Vedanta questions
        "questionText": question.strip(),  # Using camelCase to match reference schema
        "normalizedText": question_normalized,
        "canonical_text": canonical_text,  # Keep for our use case
        "topics": topics,
        "entities": entities,
        "tags": tags or [],  # Broader/UI-facing tags
        "video_link": video_link,  # Keep for our video use case
        "full_video_link": full_video_link,
        "playlist_link": playlist_link,
        "embedding": embedding,  # Vector embedding for semantic search
        "embeddingModel": embedding_model,  # e.g., "text-embedding-3-large"
        "embeddingDim": embedding_dim,  # Dimension of embedding vector
        "voteUp": 0,  # Using camelCase to match reference schema
        "timesAsked": 1,  # Track how many times question was asked
        "status": "active",  # active | hidden | archived
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
        # Backward compatibility fields (keep for migration)
        "question": question.strip(),
        "question_normalized": question_normalized,
        "votes": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    try:
        container.create_item(body=question_doc)
        return question_doc
    except exceptions.CosmosAccessConditionFailedError:
        # Race condition - question was added by another request
        existing = find_question_by_text(question)
        if existing:
            return existing
        raise

def upvote_question(question: str) -> Dict:
    """
    Upvote a question. Creates it if it doesn't exist.
    Returns the updated question document.
    """
    container = get_cosmos_container()
    question_normalized = normalize_question(question)
    
    # Try to find existing question
    existing = find_question_by_text(question)
    
    if existing:
        # Update existing question - support both old and new schema
        current_votes = existing.get("voteUp", existing.get("votes", existing.get("upvotes", 0)))
        existing["voteUp"] = current_votes + 1
        # Update timesAsked
        existing["timesAsked"] = existing.get("timesAsked", 0) + 1
        existing["updatedAt"] = datetime.utcnow().isoformat()
        # Keep backward compatibility
        if "votes" in existing:
            existing["votes"] = existing["voteUp"]
        if "updated_at" in existing:
            existing["updated_at"] = existing["updatedAt"]
        
        try:
            container.replace_item(item=existing["id"], body=existing)
            return existing
        except exceptions.CosmosHttpResponseError as e:
            print(f"Error upvoting question: {e}")
            raise
    else:
        # Create new question with 1 vote - process question for computed values
        try:
            processed = process_question(question)
            canonical_text = processed["canonical_text"]
            topics = processed["topics"]
            entities = processed["entities"]
        except Exception as e:
            print(f"Error processing question: {e}")
            canonical_text = question.lower()
            topics = []
            entities = []
        
        question_id = str(uuid.uuid4())
        question_doc = {
            "id": question_id,
            "domain": "philosophy",  # Default for Vedanta questions
            "questionText": question.strip(),
            "normalizedText": question_normalized,
            "canonical_text": canonical_text,
            "topics": topics,
            "entities": entities,
            "tags": [],
            "video_link": None,
            "full_video_link": None,
            "playlist_link": None,
            "embedding": None,
            "embeddingModel": None,
            "embeddingDim": None,
            "voteUp": 1,
            "timesAsked": 1,
            "status": "active",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            # Backward compatibility
            "question": question.strip(),
            "question_normalized": question_normalized,
            "votes": 1,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        try:
            container.create_item(body=question_doc)
            return question_doc
        except exceptions.CosmosAccessConditionFailedError:
            # Race condition - try to get existing
            existing = find_question_by_text(question)
            if existing:
                return upvote_question(question)  # Retry upvote
            raise

def find_question_by_text(question: str) -> Optional[Dict]:
    """Find a question by its text (case-insensitive)"""
    container = get_cosmos_container()
    question_normalized = normalize_question(question)
    
    # Support both old and new field names
    query = "SELECT * FROM c WHERE c.normalizedText = @normalized OR c.question_normalized = @normalized"
    parameters = [{"name": "@normalized", "value": question_normalized}]
    
    items = list(container.query_items(
        query=query,
        parameters=parameters,
        enable_cross_partition_query=True
    ))
    
    return items[0] if items else None

def get_question_by_id(question_id: str) -> Optional[Dict]:
    """Get a question by its ID"""
    container = get_cosmos_container()
    try:
        return container.read_item(item=question_id, partition_key=question_id)
    except exceptions.CosmosResourceNotFoundError:
        return None

def get_questions_queue(limit: int = 50, sort_by: str = "votes") -> List[Dict]:
    """
    Get questions from the queue, sorted by votes (descending).
    Only returns questions WITHOUT video_link (unanswered questions).
    
    Args:
        limit: Maximum number of questions to return
        sort_by: Field to sort by ("votes" or "created_at")
    """
    container = get_cosmos_container()
    
    # Only get questions WITHOUT video_link (unanswered questions in queue)
    query = """
    SELECT * FROM c
    WHERE (NOT IS_DEFINED(c.video_link) OR c.video_link = null OR c.video_link = '')
    """
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    # Sort in Python to support both old and new schema
    if sort_by == "votes" or sort_by == "upvotes" or sort_by == "voteUp":
        items.sort(key=lambda x: x.get("voteUp", x.get("votes", x.get("upvotes", 0))), reverse=True)
    else:
        items.sort(key=lambda x: x.get("createdAt", x.get("created_at", "")), reverse=True)
    
    return items[:limit]

def find_similar_questions_in_queue(user_question: str, limit: int = 5) -> List[Dict]:
    """
    Find similar questions in the queue that might be duplicates or related.
    Uses simple text matching for now (can be enhanced with LLM later).
    """
    container = get_cosmos_container()
    user_question_normalized = normalize_question(user_question)
    
    # Get all questions and filter for similarity
    all_questions = get_questions_queue(limit=100)
    
    similar = []
    user_words = set(user_question_normalized.split())
    
    for q in all_questions:
        q_text_normalized = q.get("question_normalized", "")
        q_words = set(q_text_normalized.split())
        
        # Simple similarity: check if questions share significant words
        if q_text_normalized != user_question_normalized:
            common_words = user_words.intersection(q_words)
            if len(common_words) >= 2:  # At least 2 common words
                similar.append(q)
    
    # Sort by votes (support both old and new schema) and return top matches
    similar.sort(key=lambda x: x.get("voteUp", x.get("votes", x.get("upvotes", 0))), reverse=True)
    return similar[:limit]

def get_question_stats() -> Dict:
    """Get statistics about questions in the queue"""
    container = get_cosmos_container()
    
    query = "SELECT VALUE COUNT(1) FROM c"
    total_count = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))[0]
    
    # Get all items and sum votes in Python (Cosmos DB doesn't support ?? operator)
    query = "SELECT * FROM c"
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    # Sum votes (support both old and new schema)
    total_votes = sum(item.get("voteUp", item.get("votes", item.get("upvotes", 0))) for item in items)
    
    return {
        "total_questions": total_count,
        "total_votes": total_votes
    }

