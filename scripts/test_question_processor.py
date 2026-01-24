#!/usr/bin/env python3
"""
Quick test script to verify question processor is working.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.question_processor import process_question

test_question = "What is the vedantic view of evolution?"

print(f"Testing question processor with: '{test_question}'")
print("-" * 60)

try:
    result = process_question(test_question)
    print("✓ Success!")
    print(f"Canonical text: {result['canonical_text']}")
    print(f"Topics: {result['topics']}")
    print(f"Entities: {result['entities']}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
