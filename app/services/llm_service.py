import os
import json
from typing import List, Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize OpenAI client
client = None

def get_openai_client():
    """Initialize and return OpenAI client"""
    global client
    if client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        client = OpenAI(api_key=api_key)
    return client

# Cache for questions data
_questions_cache = None
_video_title_cache = None
_playlist_id_cache = None
# Cache for LLM matching results (only for precanned questions)
_match_cache = {}

# Precanned questions that should be cached for idempotency
PRECANNED_QUESTIONS = [
    "Why should I care about spirituality?",
    "What is the nature of consciousness?",
    "How does Vedanta view suffering?",
    "In Vedanta, are we ignoring the problems of society for the sake of spirituality?"
]

def is_precanned_question(user_query: str) -> bool:
    """Check if a query is one of the precanned questions"""
    query_normalized = user_query.strip().lower()
    return any(query_normalized == pq.strip().lower() for pq in PRECANNED_QUESTIONS)

def load_questions() -> List[Dict]:
    """Load questions from JSON file"""
    global _questions_cache
    if _questions_cache is None:
        # Try multiple possible paths
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '../../askswami_questions.json'),
            'askswami_questions.json',
            os.path.join(os.getcwd(), 'askswami_questions.json')
        ]
        
        for json_path in possible_paths:
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    _questions_cache = json.load(f)
                break
        
        if _questions_cache is None:
            raise FileNotFoundError("askswami_questions.json not found")
    
    return _questions_cache

def get_playlist_id_lookup() -> Dict[str, str]:
    """Create a lookup dictionary mapping video_id to playlist_id"""
    global _playlist_id_cache
    if _playlist_id_cache is None:
        _playlist_id_cache = {}
        # Try multiple possible paths
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '../../askswami_chapters.json'),
            'askswami_chapters.json',
            os.path.join(os.getcwd(), 'askswami_chapters.json')
        ]
        
        chapters_path = None
        for json_path in possible_paths:
            if os.path.exists(json_path):
                chapters_path = json_path
                break
        
        if chapters_path:
            with open(chapters_path, 'r', encoding='utf-8') as f:
                chapters = json.load(f)
                for chapter in chapters:
                    video_id = chapter.get('video_id')
                    playlist_id = chapter.get('playlist_id')
                    if video_id and playlist_id:
                        # Only store if not already present (first occurrence wins)
                        if video_id not in _playlist_id_cache:
                            _playlist_id_cache[video_id] = playlist_id
    
    return _playlist_id_cache

def get_playlist_id(video_id: str) -> Optional[str]:
    """Get playlist_id for a given video_id"""
    lookup = get_playlist_id_lookup()
    return lookup.get(video_id)

def match_question_with_llm(user_query: str, top_n: int = 3) -> List[Dict]:
    """
    Match user query to questions using LLM with strict relevance filtering
    
    Args:
        user_query: User's question
        top_n: Maximum number of top matches to return (may return fewer if not enough highly relevant matches)
    
    Returns:
        List of matched questions with url and timestamp (only highly relevant ones)
    """
    # Check cache only for precanned questions (for idempotency)
    should_cache = is_precanned_question(user_query)
    cache_key = None
    if should_cache:
        cache_key = f"{user_query.lower().strip()}:{top_n}"
        if cache_key in _match_cache:
            return _match_cache[cache_key]
    
    questions = load_questions()
    
    # Format questions for LLM context
    questions_text = "\n".join([
        f"{i+1}. {q['question']}"
        for i, q in enumerate(questions)
    ])
    
    # Step 1: Get initial candidates (more than we need)
    initial_matches = min(top_n * 3, 15)  # Get more candidates for filtering
    
    prompt = f"""You are helping match user questions to existing Q&A video segments.

User's question: "{user_query}"

Here are all available questions from Q&A videos (519 total):

{questions_text}

Find up to {initial_matches} question numbers that could potentially match the user's question.
Return ONLY a valid JSON array with the question numbers (1-based index), ordered by potential relevance.
Example: [5, 23, 101]

Return only the JSON array, no other text:"""

    try:
        openai_client = get_openai_client()
        
        # Step 1: Get candidates (temperature=0 for deterministic results)
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that matches questions. Always return valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,  # Set to 0 for deterministic/idempotent results
            max_tokens=150
        )
        
        # Parse response
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        indices = json.loads(result_text)
        
        # Get candidate questions (deduplicate by URL to avoid same question appearing multiple times)
        candidates = []
        seen_urls = set()
        for idx in indices[:initial_matches]:
            if 1 <= idx <= len(questions):
                question_data = questions[idx - 1].copy()
                question_url = question_data.get('url', '')
                # Extract base URL (without timestamp) for deduplication
                base_url = question_url.split('&t=')[0] if '&t=' in question_url else question_url
                if base_url not in seen_urls:
                    seen_urls.add(base_url)
                    question_data['question_text'] = question_data['question']
                    candidates.append(question_data)
        
        if not candidates:
            return []
        
        # Step 2: Strict relevance validation - only keep highly relevant matches
        candidates_text = "\n".join([
            f"{i+1}. {c['question']}"
            for i, c in enumerate(candidates)
        ])
        
        validation_prompt = f"""You are helping match user questions to existing Q&A video segments.

User's question: "{user_query}"

Candidate matches:
{candidates_text}

Return question numbers (1-based from the candidate list above) that are relevant to the user's question.
Include questions that are semantically similar or address related topics.

Return up to {top_n} question numbers, ordered by relevance (most relevant first).
Return ONLY a valid JSON array with the question numbers from the candidate list (1-based).
Example: [1, 3, 5]

Return only the JSON array, no other text:"""
        
        validation_response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful relevance filter. Return up to the requested number of relevant matches. Always return valid JSON arrays."},
                {"role": "user", "content": validation_prompt}
            ],
            temperature=0,  # Set to 0 for deterministic/idempotent results
            max_tokens=150  # Increased to allow for more results
        )
        
        validation_text = validation_response.choices[0].message.content.strip()
        if validation_text.startswith("```"):
            validation_text = validation_text.split("```")[1]
            if validation_text.startswith("json"):
                validation_text = validation_text[4:]
        validation_text = validation_text.strip()
        
        validated_indices = json.loads(validation_text)
        
        # Handle empty array (no relevant matches found)
        if not validated_indices or len(validated_indices) == 0:
            return []
        
        # Deduplicate indices (in case LLM returns same index multiple times)
        seen_indices = set()
        unique_indices = []
        for idx in validated_indices:
            if idx not in seen_indices and 1 <= idx <= len(candidates):
                seen_indices.add(idx)
                unique_indices.append(idx)
        
        # Get final matches (convert candidate list index to actual question, deduplicate by URL)
        final_matches = []
        seen_urls = set()
        for idx in unique_indices[:top_n]:
            if 1 <= idx <= len(candidates):
                match = candidates[idx - 1].copy()
                # Deduplicate by base URL (same video, different timestamps are still considered duplicates)
                match_url = match.get('url', '')
                base_url = match_url.split('&t=')[0] if '&t=' in match_url else match_url
                if base_url not in seen_urls:
                    seen_urls.add(base_url)
                    match['match_rank'] = len(final_matches) + 1
                    final_matches.append(match)
        
        # Cache the result only for precanned questions (for idempotency)
        if should_cache and cache_key:
            _match_cache[cache_key] = final_matches
        
        return final_matches
    
    except Exception as e:
        print(f"Error in LLM matching: {e}")
        # Fallback: return empty or use simple keyword matching
        return []

def find_related_questions(user_query: str, num_questions: int = 3) -> List[str]:
    """
    Find related questions from the database that are similar to the user's query.
    Used as fallback when no direct matches are found.
    
    Args:
        user_query: User's question
        num_questions: Number of related questions to return (2-3)
    
    Returns:
        List of related question texts from the database
    """
    questions = load_questions()
    
    if not questions:
        return []
    
    # Format questions for LLM context
    questions_text = "\n".join([
        f"{i+1}. {q['question']}"
        for i, q in enumerate(questions)
    ])
    
    prompt = f"""A user asked this question but we couldn't find a direct answer: "{user_query}"

Here are all available questions from Q&A videos (519 total):

{questions_text}

Find {num_questions} question numbers (1-based index) from the list above that are most related or similar to the user's question, even if they don't directly answer it.
These should be questions that explore similar topics or themes.

Return ONLY a valid JSON array with the question numbers, ordered by relevance.
Example: [42, 156, 203]

Return only the JSON array, no other text:"""
    
    try:
        openai_client = get_openai_client()
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that finds related questions. Always return valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=50
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        indices = json.loads(result_text)
        
        # Get related questions
        related_questions = []
        for idx in indices[:num_questions]:
            if 1 <= idx <= len(questions):
                question_text = questions[idx - 1].get('question', '')
                if question_text:
                    related_questions.append(question_text)
        
        return related_questions
    
    except Exception as e:
        print(f"Error finding related questions: {e}")
        return []

def get_related_question(user_query: str, matched_questions: List[str]) -> Optional[str]:
    """
    Generate a related question based on user query and matched results
    
    Args:
        user_query: Original user question
        matched_questions: List of matched question texts
    
    Returns:
        A related question to explore next, or None
    """
    if not matched_questions:
        return None
    
    try:
        openai_client = get_openai_client()
        
        matched_text = "\n".join([f"- {q}" for q in matched_questions[:3]])
        
        prompt = f"""Based on this user question and the answers they found, suggest ONE related question they might want to explore next.

User's question: "{user_query}"

Answers they found:
{matched_text}

Suggest ONE related question (different from the user's question) that would be a natural follow-up or explore a related aspect.
Return ONLY the question text, nothing else."""

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that suggests related questions. Return only the question text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        related_q = response.choices[0].message.content.strip()
        # Clean up if it has quotes
        related_q = related_q.strip('"').strip("'")
        return related_q if related_q else None
    
    except Exception as e:
        print(f"Error generating related question: {e}")
        return None

