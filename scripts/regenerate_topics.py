#!/usr/bin/env python3
"""
Script to regenerate topics by splitting "Other" into "AI" and another topic.
"""

import json
import re
from pathlib import Path

def is_ai_related(chapter_title: str) -> bool:
    """Check if a chapter title is AI-related."""
    title_lower = chapter_title.lower()
    
    # More specific AI keywords
    ai_keywords = [
        ' ai ',
        ' artificial intelligence',
        ' chatgpt',
        ' machine learning',
        ' neural network',
        ' algorithm',
        ' robot',
        ' automation',
        ' super-intelligence',
        ' superintelligence',
        ' artificial',
        ' ai?',
        ' ai.',
        ' ai,',
        ' ai:',
        ' ai;',
    ]
    
    # Check for AI keywords as whole words or at word boundaries
    for keyword in ai_keywords:
        if keyword in title_lower:
            return True
    
    # Check for "AI" as a standalone word (not part of another word)
    if re.search(r'\bai\b', title_lower):
        return True
    
    return False

def categorize_other_questions(chapter_title: str) -> str:
    """Categorize questions that were in 'Other' into appropriate topics."""
    title_lower = chapter_title.lower()
    
    # Skip "Intro" entries
    if title_lower.strip() == 'intro':
        return 'Other'
    
    # Check for AI first
    if is_ai_related(chapter_title):
        return 'AI'
    
    # Check for philosophy/concepts topics
    philosophy_keywords = [
        'brahman',
        'jiva',
        'jivatman',
        'advaita',
        'non-duality',
        'nonduality',
        'maya',
        'atman',
        'neti neti',
        'consciousness',
        'reality',
        'duality',
        'oneness',
        'self',
        'guru',
        'vedanta',
        'philosophy',
        'teaching',
        'concept',
    ]
    
    # If it contains philosophy keywords, categorize as "Philosophy & Concepts"
    if any(keyword in title_lower for keyword in philosophy_keywords):
        return 'Philosophy & Concepts'
    
    # Everything else stays as "Other"
    return 'Other'

def regenerate_topics():
    """Regenerate topics by updating the JSON file."""
    json_path = Path(__file__).parent.parent / "askswami_chapters_tagged.json"
    
    if not json_path.exists():
        print(f"Error: {json_path} not found")
        return
    
    # Load the JSON file
    print(f"Loading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        chapters = json.load(f)
    
    print(f"Total chapters: {len(chapters)}")
    
    # Count original topics
    original_counts = {}
    for chapter in chapters:
        tag = chapter.get('primary_tag', 'Other')
        original_counts[tag] = original_counts.get(tag, 0) + 1
    
    print("\nOriginal topic counts:")
    for tag, count in sorted(original_counts.items()):
        print(f"  {tag}: {count}")
    
    # Update chapters that have "Other" as primary_tag
    updated_count = 0
    ai_count = 0
    philosophy_count = 0
    other_count = 0
    
    for chapter in chapters:
        if chapter.get('primary_tag') == 'Other':
            new_tag = categorize_other_questions(chapter.get('chapter_title', ''))
            chapter['primary_tag'] = new_tag
            
            # Update tags array if it exists
            if 'tags' in chapter:
                # Remove "Other" if present
                if 'Other' in chapter['tags']:
                    chapter['tags'].remove('Other')
                # Add new tag if not already present
                if new_tag not in chapter['tags']:
                    chapter['tags'].append(new_tag)
            
            updated_count += 1
            if new_tag == 'AI':
                ai_count += 1
            elif new_tag == 'Philosophy & Concepts':
                philosophy_count += 1
            else:
                other_count += 1
    
    print(f"\nUpdated {updated_count} chapters:")
    print(f"  AI: {ai_count}")
    print(f"  Philosophy & Concepts: {philosophy_count}")
    print(f"  Other (remaining): {other_count}")
    
    # Count new topics
    new_counts = {}
    for chapter in chapters:
        tag = chapter.get('primary_tag', 'Other')
        new_counts[tag] = new_counts.get(tag, 0) + 1
    
    print("\nNew topic counts:")
    for tag, count in sorted(new_counts.items()):
        print(f"  {tag}: {count}")
    
    # Create backup
    backup_path = json_path.with_suffix('.json.backup')
    print(f"\nCreating backup: {backup_path}")
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    
    # Write updated JSON
    print(f"Writing updated JSON to {json_path}...")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, indent=2, ensure_ascii=False)
    
    print("\nDone! Topics have been regenerated.")
    print(f"Backup saved to: {backup_path}")

if __name__ == '__main__':
    regenerate_topics()
