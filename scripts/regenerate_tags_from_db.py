#!/usr/bin/env python3
"""
Script to regenerate tags from Cosmos DB topics.
- Uses topics with 5+ questions as main tags
- Groups others into "Other"
- Ensures questions with "consciousness" are tagged as "Consciousness"
- Excludes "Vedanta" and "Spirituality" as they're too general
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cosmos_service import get_cosmos_container

load_dotenv()

def regenerate_tags_from_db():
    """Regenerate tags from Cosmos DB topics."""
    container = get_cosmos_container()
    
    # Query all questions
    print("Querying all questions from Cosmos DB...")
    query = "SELECT c.id, c.questionText, c.topics FROM c"
    items = list(container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))
    
    print(f"Total questions in DB: {len(items)}")
    
    # Exclude these topics as they're too general
    excluded_topics = {'vedanta', 'spirituality', 'spiritual'}
    
    # Count topics
    topic_counts = Counter()
    
    for item in items:
        topics = item.get('topics', [])
        if isinstance(topics, list):
            for topic in topics:
                if topic:
                    topic_lower = topic.lower().strip()
                    if topic_lower not in excluded_topics:
                        topic_counts[topic_lower] += 1
    
    # Get topics with 5+ questions (main tags)
    min_questions = 5
    main_topics = {topic: count for topic, count in topic_counts.items() if count >= min_questions}
    
    # Topic name normalization mapping
    topic_name_map = {
        'artificial intelligence': 'AI',
        'consciousness': 'Consciousness',
        'philosophy': 'Philosophy',
        'meditation': 'Meditation',
        'enlightenment': 'Enlightenment',
        'advaita': 'Advaita',
        'karma': 'Karma',
        'suffering': 'Suffering & Ethics',  # Combine with Ethics
        'ethics': 'Suffering & Ethics',
        'maya': 'Maya',
        'mind': 'Mind',
        'sleep': 'Sleep',
        'buddhism': 'Buddhism',
        'theology': 'Theology',
        'bhakti': 'God & Devotion',  # Combine with Devotion
        'devotion': 'God & Devotion',
        'reality': 'Reality',
        'realization': 'Realization',
        'reincarnation': 'Reincarnation',
        'experience': 'Experience',
        'free will': 'Free Will',
        'mindfulness': 'Mindfulness',
        'non-duality': 'Non-Duality',
        'personal development': 'Personal Development',
        'prayer': 'Prayer',
        'science': 'Science',
        'spiritual life': 'Spiritual Life',
        'spiritual practice': 'Spiritual Practice',
        'universe': 'Universe',
        'yoga': 'Yoga',
    }
    
    print(f"\nTopics with {min_questions}+ questions (will be main tags): {len(main_topics)}")
    print("Main topics:")
    for topic, count in sorted(main_topics.items(), key=lambda x: (-x[1], x[0])):
        display_name = topic_name_map.get(topic, topic.title())
        print(f"  {display_name}: {count}")
    
    # Load the tagged chapters JSON
    json_path = Path(__file__).parent.parent / "askswami_chapters_tagged.json"
    if not json_path.exists():
        print(f"\nError: {json_path} not found")
        return
    
    print(f"\nLoading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    print(f"Total chapters: {len(chapters)}")
    
    # Create a mapping from question text to primary tag
    question_to_tag = {}
    updated_count = 0
    consciousness_count = 0
    other_count = 0
    
    # First pass: check for consciousness in question text
    for chapter in chapters:
        chapter_title = chapter.get('chapter_title', '')
        if 'consciousness' in chapter_title.lower():
            question_to_tag[chapter_title.lower()] = 'Consciousness'
            consciousness_count += 1
    
    # Second pass: assign tags based on topics
    for chapter in chapters:
        chapter_title = chapter.get('chapter_title', '')
        chapter_title_lower = chapter_title.lower()
        
        # Skip if already assigned to Consciousness
        if chapter_title_lower in question_to_tag:
            continue
        
        # Skip "Intro" entries
        if chapter_title_lower.strip() == 'intro':
            question_to_tag[chapter_title_lower] = 'Other'
            continue
        
        # Find matching question in DB
        matching_question = None
        for item in items:
            question_text = item.get('questionText', '')
            if question_text.lower() == chapter_title_lower:
                matching_question = item
                break
        
        assigned_tag = None
        
        if matching_question:
            # Get topics from DB
            topics = matching_question.get('topics', [])
            if isinstance(topics, list):
                # Find first topic that's in our main topics list
                # Prioritize topics that appear earlier in the list
                for topic in topics:
                    if topic:
                        topic_lower = topic.lower().strip()
                        if topic_lower in main_topics:
                            # Use normalized name from mapping, or capitalize
                            assigned_tag = topic_name_map.get(topic_lower, topic_lower.title())
                            break
                # If no direct match, check if any topic maps to a main tag
                if not assigned_tag:
                    for topic in topics:
                        if topic:
                            topic_lower = topic.lower().strip()
                            mapped_tag = topic_name_map.get(topic_lower)
                            if mapped_tag and mapped_tag != 'Other':
                                # Check if this mapped tag corresponds to a main topic
                                # (e.g., "suffering" -> "Suffering & Ethics")
                                mapped_lower = mapped_tag.lower()
                                # Check if any main topic matches this mapped tag
                                for main_topic in main_topics:
                                    if main_topic in mapped_lower or mapped_lower in main_topic:
                                        assigned_tag = mapped_tag
                                        break
                                if assigned_tag:
                                    break
        
        # If no main topic found, assign to "Other"
        if not assigned_tag:
            assigned_tag = 'Other'
            other_count += 1
        
        question_to_tag[chapter_title_lower] = assigned_tag
    
    # Update chapters
    for chapter in chapters:
        chapter_title = chapter.get('chapter_title', '')
        chapter_title_lower = chapter_title.lower()
        
        new_tag = question_to_tag.get(chapter_title_lower, 'Other')
        old_tag = chapter.get('primary_tag', 'Other')
        
        if new_tag != old_tag:
            chapter['primary_tag'] = new_tag
            updated_count += 1
            
            # Update tags array
            if 'tags' in chapter:
                # Remove old primary tag if present
                if old_tag in chapter['tags']:
                    chapter['tags'].remove(old_tag)
                # Add new tag if not already present
                if new_tag not in chapter['tags']:
                    chapter['tags'].append(new_tag)
    
    # Final pass: ensure all tags have at least 5 entries in JSON file
    # Count tags after initial assignment
    tag_counts_final = Counter()
    for chapter in chapters:
        tag = chapter.get('primary_tag', 'Other')
        tag_counts_final[tag] += 1
    
    # Move tags with < 5 entries to "Other"
    tags_to_merge = [tag for tag, count in tag_counts_final.items() if count < 5 and tag != 'Other']
    
    if tags_to_merge:
        print(f"\nMoving {len(tags_to_merge)} tags with < 5 entries to 'Other':")
        for tag in sorted(tags_to_merge):
            count = tag_counts_final[tag]
            print(f"  {tag}: {count} -> Other")
        
        merged_count = 0
        for chapter in chapters:
            current_tag = chapter.get('primary_tag', 'Other')
            if current_tag in tags_to_merge:
                old_tag = current_tag
                chapter['primary_tag'] = 'Other'
                merged_count += 1
                
                # Update tags array
                if 'tags' in chapter:
                    if old_tag in chapter['tags']:
                        chapter['tags'].remove(old_tag)
                    if 'Other' not in chapter['tags']:
                        chapter['tags'].append('Other')
        
        print(f"  Merged {merged_count} chapters into 'Other'")
    
    print(f"\nUpdated {updated_count} chapters:")
    print(f"  Consciousness (from text): {consciousness_count}")
    print(f"  Other: {other_count}")
    
    # Count final tags
    final_counts = Counter()
    for chapter in chapters:
        tag = chapter.get('primary_tag', 'Other')
        final_counts[tag] += 1
    
    print("\nFinal tag counts (all tags have 5+ entries):")
    for tag, count in sorted(final_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {tag}: {count}")
    
    # Create backup
    backup_path = json_path.with_suffix('.json.backup2')
    print(f"\nCreating backup: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    
    # Write updated JSON
    print(f"Writing updated JSON to {json_path}...")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    
    print("\nDone! Tags have been regenerated from database topics.")
    print(f"Backup saved to: {backup_path}")

if __name__ == '__main__':
    regenerate_tags_from_db()
