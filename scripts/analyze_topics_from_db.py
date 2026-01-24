#!/usr/bin/env python3
"""
Script to analyze topics from Cosmos DB to see if we can use them as tags.
Excludes "Vedanta" and "Spirituality" as they apply to most questions.
Also checks for "consciousness" in question text.
"""

import os
import sys
from pathlib import Path
from collections import Counter, defaultdict
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cosmos_service import get_cosmos_container

load_dotenv()

def analyze_topics_from_db():
    """Analyze all topics from Cosmos DB questions."""
    container = get_cosmos_container()
    
    # Query all questions
    print("Querying all questions from Cosmos DB...")
    query = "SELECT c.id, c.questionText, c.topics, c.entities FROM c"
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    print(f"Total questions in DB: {len(items)}")
    
    # Exclude these topics as they're too general
    excluded_topics = {'vedanta', 'spirituality', 'spiritual'}
    
    # Count topics
    topic_counts = Counter()
    topic_question_map = defaultdict(list)  # Map topic to question texts
    
    # Also track questions with "consciousness" in the text
    consciousness_questions = []
    
    for item in items:
        question_text = item.get('questionText', '')
        topics = item.get('topics', [])
        
        # Check if question contains "consciousness"
        if 'consciousness' in question_text.lower():
            consciousness_questions.append(question_text[:80])
        
        # Process topics
        if isinstance(topics, list):
            for topic in topics:
                if topic:  # Skip empty topics
                    topic_lower = topic.lower().strip()
                    # Exclude general topics
                    if topic_lower not in excluded_topics:
                        topic_counts[topic_lower] += 1
                        topic_question_map[topic_lower].append(question_text[:80])
    
    print(f"\nQuestions containing 'consciousness': {len(consciousness_questions)}")
    if consciousness_questions:
        print("Sample consciousness questions:")
        for q in consciousness_questions[:5]:
            print(f"  - {q}...")
    
    print(f"\nUnique topics (excluding Vedanta/Spirituality): {len(topic_counts)}")
    print("\nTopic counts (sorted by frequency):")
    print("-" * 80)
    
    # Sort by count, then alphabetically
    sorted_topics = sorted(topic_counts.items(), key=lambda x: (-x[1], x[0]))
    
    # Show all topics with counts
    for topic, count in sorted_topics:
        print(f"  {topic.capitalize()}: {count}")
    
    # Show distribution
    print("\n" + "=" * 80)
    print("Topic distribution:")
    print(f"  Topics with 1 question: {sum(1 for _, count in sorted_topics if count == 1)}")
    print(f"  Topics with 2-5 questions: {sum(1 for _, count in sorted_topics if 2 <= count <= 5)}")
    print(f"  Topics with 6-10 questions: {sum(1 for _, count in sorted_topics if 6 <= count <= 10)}")
    print(f"  Topics with 11-20 questions: {sum(1 for _, count in sorted_topics if 11 <= count <= 20)}")
    print(f"  Topics with 21+ questions: {sum(1 for _, count in sorted_topics if count >= 21)}")
    
    # Show top 20 topics
    print("\n" + "=" * 80)
    print("Top 20 topics by question count:")
    print("-" * 80)
    for i, (topic, count) in enumerate(sorted_topics[:20], 1):
        print(f"{i:2d}. {topic.capitalize()}: {count} questions")
        # Show a sample question
        if topic_question_map[topic]:
            print(f"    Sample: {topic_question_map[topic][0]}...")
    
    # Check if we'd have too many topics
    print("\n" + "=" * 80)
    print("Analysis:")
    print(f"  Total unique topics: {len(topic_counts)}")
    
    # Count topics that would be useful as tags (e.g., >= 2 questions)
    useful_topics = [t for t, c in sorted_topics if c >= 2]
    print(f"  Topics with 2+ questions (potentially useful as tags): {len(useful_topics)}")
    
    # Count topics that would be very useful (e.g., >= 5 questions)
    very_useful_topics = [t for t, c in sorted_topics if c >= 5]
    print(f"  Topics with 5+ questions (very useful as tags): {len(very_useful_topics)}")
    
    if len(topic_counts) > 50:
        print(f"\n⚠️  WARNING: {len(topic_counts)} topics might be too many for a clean UI.")
        print("   Consider using only topics with 3+ questions, or grouping similar topics.")
    elif len(topic_counts) > 30:
        print(f"\n⚠️  NOTE: {len(topic_counts)} topics is manageable but might be crowded.")
    else:
        print(f"\n✓ {len(topic_counts)} topics is a reasonable number for tags.")
    
    # Show topics that might need grouping
    print("\n" + "=" * 80)
    print("Topics with only 1 question (might need grouping or 'Other' category):")
    single_question_topics = [t for t, c in sorted_topics if c == 1]
    if single_question_topics:
        print(f"  Total: {len(single_question_topics)}")
        print("  Sample (first 20):")
        for topic in single_question_topics[:20]:
            print(f"    - {topic.capitalize()}")
        if len(single_question_topics) > 20:
            print(f"    ... and {len(single_question_topics) - 20} more")

if __name__ == '__main__':
    analyze_topics_from_db()
