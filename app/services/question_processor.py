"""
Service for processing questions and extracting computed values:
- Canonical text (stripped down to bare minimum)
- Topics (array of topics)
- Entities (array of entity objects with type and name)
"""

import json
from typing import List, Dict, Optional
from app.services.llm_service import get_openai_client


def compute_canonical_text(question: str) -> str:
    """
    Strip a question down to its bare minimum canonical form.
    
    Examples:
    - "What is the vedantic view of evolution?" -> "vedantic view evolution"
    - "How can we better handle stress?" -> "handle stress"
    - "What does Vedanta say about the nature of consciousness?" -> "Vedanta nature consciousness"
    
    Args:
        question: Original question text
    
    Returns:
        Canonical text (minimal, essential keywords)
    """
    try:
        openai_client = get_openai_client()
        
        prompt = f"""Extract the canonical (minimal) form of this question by removing all filler words and keeping only the essential core concepts.

Question: "{question}"

Return ONLY the canonical text (2-5 words max), nothing else. No quotes, no explanation.

Examples:
- "What is the vedantic view of evolution?" -> vedantic view evolution
- "How can we better handle stress?" -> handle stress
- "What does Vedanta say about the nature of consciousness?" -> Vedanta nature consciousness
- "Why should I care about spirituality?" -> spirituality importance

Canonical text:"""

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You extract canonical forms of questions. Return only the canonical text, no quotes or explanations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=30
        )
        
        canonical = response.choices[0].message.content.strip()
        # Remove quotes if present
        canonical = canonical.strip('"').strip("'").strip()
        return canonical if canonical else question.lower()
    
    except Exception as e:
        print(f"Error computing canonical text: {e}")
        # Fallback: return lowercase question
        return question.lower()


def extract_topics_and_entities(question: str) -> Dict[str, any]:
    """
    Extract topics and entities from a question.
    
    Topics are general subject areas (e.g., "evolution", "vedanta", "consciousness", "stress")
    Entities are specific named things (people, places, concepts) with types
    
    Args:
        question: Question text
    
    Returns:
        Dictionary with "topics" (list of strings) and "entities" (list of dicts with "type" and "name")
    """
    try:
        openai_client = get_openai_client()
        
        prompt = f"""Extract topics and entities from this question.

Question: "{question}"

Topics are general subject areas or themes (e.g., "evolution", "consciousness", "stress", "meditation", "suffering", "karma").
IMPORTANT: Do NOT include "Vedanta" or "Spirituality" as topics, as these apply to most questions in this domain and are not useful for filtering.

Entities are specific named things with types:
- person: Names of people (e.g., "Buddha", "Shankara", "Sri Sri Ravishankar")
- concept: Specific philosophical or spiritual concepts (e.g., "Advaita", "Maya", "Brahman")
- place: Geographic locations (e.g., "India", "New York")
- text: Sacred texts or books (e.g., "Bhagavad Gita", "Upanishads")

Return a JSON object with:
- "topics": array of topic strings (excluding "Vedanta" and "Spirituality")
- "entities": array of objects, each with "type" and "name"

Examples:
Question: "What is the vedantic view of evolution?"
{{
  "topics": ["evolution"],
  "entities": []
}}

Question: "What does Vedanta say about Buddha's teachings?"
{{
  "topics": ["buddhism"],
  "entities": [{{"type": "person", "name": "Buddha"}}]
}}

Question: "How does Advaita explain Maya?"
{{
  "topics": ["advaita", "maya"],
  "entities": [
    {{"type": "concept", "name": "Advaita"}},
    {{"type": "concept", "name": "Maya"}}
  ]
}}

Question: "Why should I care about spirituality?"
{{
  "topics": [],
  "entities": []
}}

Return ONLY the JSON object, no other text:"""

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You extract topics and entities from questions. Always return valid JSON objects with 'topics' (array of strings) and 'entities' (array of objects with 'type' and 'name'). Never include 'Vedanta' or 'Spirituality' as topics, as these are too common and not useful for filtering."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=200
        )
        
        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        result = json.loads(result_text)
        
        # Ensure proper format
        topics = result.get("topics", [])
        entities = result.get("entities", [])
        
        # Filter out common topics that apply to most questions
        excluded_topics = {"vedanta", "spirituality", "spiritual"}
        filtered_topics = [
            topic for topic in topics 
            if isinstance(topic, str) and topic.lower() not in excluded_topics
        ]
        
        # Validate entities have type and name
        validated_entities = []
        for entity in entities:
            if isinstance(entity, dict) and "type" in entity and "name" in entity:
                validated_entities.append({
                    "type": entity["type"],
                    "name": entity["name"]
                })
        
        return {
            "topics": filtered_topics,
            "entities": validated_entities
        }
    
    except Exception as e:
        print(f"Error extracting topics and entities: {e}")
        # Fallback: return empty
        return {
            "topics": [],
            "entities": []
        }


def process_question(question: str) -> Dict[str, any]:
    """
    Process a question and compute all derived values.
    
    Args:
        question: Question text
    
    Returns:
        Dictionary with:
        - canonical_text: Stripped down question
        - topics: Array of topic strings
        - entities: Array of entity objects
    """
    canonical_text = compute_canonical_text(question)
    topics_entities = extract_topics_and_entities(question)
    
    return {
        "canonical_text": canonical_text,
        "topics": topics_entities["topics"],
        "entities": topics_entities["entities"]
    }
