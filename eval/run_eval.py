#!/usr/bin/env python3
"""
Evaluation script for Expert Answers API.
Runs queries from golden_set.json and compares results with expected answers.
"""

import json
import requests
import sys
from typing import Dict, List, Any
from pathlib import Path
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.json"
RESULTS_DIR = Path(__file__).parent / "results"
SCORES_FILE = Path(__file__).parent / "scores.json"


def load_golden_set() -> Dict[str, Any]:
    """Load the golden evaluation set."""
    with open(GOLDEN_SET_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def call_api(query: str, count: int = 5) -> Dict[str, Any]:
    """Call the Expert Answers API with a query."""
    url = f"{API_BASE_URL}/api/answers/v1"
    params = {
        "question": query,
        "count": count
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ❌ API Error: {e}")
        return None


def normalize_question(question: str) -> str:
    """Normalize question text for comparison (lowercase, strip whitespace)."""
    return question.lower().strip()


def find_answer_in_results(expected: Dict[str, Any], actual_results: List[Dict[str, Any]]) -> tuple[bool, int]:
    """
    Check if expected answer is in actual results.
    Returns (found, rank) where rank is 1-based position, or 0 if not found.
    """
    expected_question = normalize_question(expected["question"])
    
    for idx, result in enumerate(actual_results, start=1):
        actual_question = normalize_question(result.get("questionTitle", ""))
        
        # Check if question matches (exact or contains)
        if expected_question in actual_question or actual_question in expected_question:
            # Check URL pattern if specified
            if "url_pattern" in expected:
                url = result.get("videoLink", "")
                if expected["url_pattern"] not in url:
                    continue
            
            return True, idx
    
    return False, 0


def evaluate_query(query_data: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a single query against the API."""
    query_id = query_data["id"]
    query_text = query_data["query"]
    expected_answers = query_data.get("expected_answers", [])
    min_relevant_count = query_data.get("min_relevant_count", 1)
    max_results_to_check = query_data.get("max_results_to_check", 5)
    
    print(f"\n📝 Query {query_id}: {query_text}")
    
    # Call API - use at least count=1 (API requires count >= 1)
    # For queries that should return 0 results, we still call with count=5 to see if API returns anything
    api_count = max(max_results_to_check, 1) if max_results_to_check == 0 else max_results_to_check
    api_response = call_api(query_text, count=api_count)
    if api_response is None:
        return {
            "query_id": query_id,
            "query": query_text,
            "status": "api_error",
            "metrics": {}
        }
    
    # Get actual answers - combine "answers" (relevant) and "otherRelatedVideos" (not_relevant) into one flat list
    relevant_answers = api_response.get("answers", []) or []
    other_related = api_response.get("otherRelatedVideos", []) or []
    
    # Ensure both are lists (handle None case)
    if relevant_answers is None:
        relevant_answers = []
    if other_related is None:
        other_related = []
    
    # Combine into one flat list for evaluation (relevant first, then not_relevant)
    actual_answers = relevant_answers + other_related
    
    search_status = api_response.get("searchStatus", "unknown")
    
    print(f"  Status: {search_status}")
    print(f"  Results returned: {len(actual_answers)} (relevant: {len(relevant_answers)}, other: {len(other_related)})")
    
    # Evaluate each expected answer
    evaluation_results = []
    found_count = 0
    
    for expected in expected_answers:
        found, rank = find_answer_in_results(expected, actual_answers)
        required = expected.get("required", False)
        min_rank = expected.get("min_rank", None)
        
        result = {
            "expected_question": expected["question"],
            "found": found,
            "rank": rank,
            "required": required,
            "min_rank": min_rank,
            "rank_ok": True if not min_rank or (found and rank <= min_rank) else False
        }
        
        evaluation_results.append(result)
        
        if found:
            found_count += 1
            status = "✅" if result["rank_ok"] else "⚠️"
            print(f"  {status} Found: '{expected['question']}' at rank {rank}")
        else:
            status = "❌" if required else "⚠️"
            print(f"  {status} Missing: '{expected['question']}'")
    
    # Calculate metrics
    total_expected = len(expected_answers)
    required_expected = sum(1 for e in expected_answers if e.get("required", False))
    required_found = sum(1 for r in evaluation_results if r["required"] and r["found"])
    
    precision = found_count / len(actual_answers) if actual_answers else 0
    recall = found_count / total_expected if total_expected > 0 else 0
    required_recall = required_found / required_expected if required_expected > 0 else 1.0
    
    # Check if minimum relevant count is met
    min_count_met = len(actual_answers) >= min_relevant_count
    
    metrics = {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "required_recall": round(required_recall, 3),
        "found_count": found_count,
        "total_expected": total_expected,
        "required_found": required_found,
        "required_expected": required_expected,
        "min_relevant_count_met": min_count_met,
        "actual_results_count": len(actual_answers)
    }
    
    return {
        "query_id": query_id,
        "query": query_text,
        "status": "success",
        "search_status": search_status,
        "evaluation_results": evaluation_results,
        "metrics": metrics,
        "actual_answers": actual_answers[:max_results_to_check]  # Store for review
    }


def run_evaluation() -> Dict[str, Any]:
    """Run evaluation on all queries in the golden set."""
    print("🚀 Starting Evaluation")
    print("=" * 60)
    
    golden_set = load_golden_set()
    queries = golden_set.get("queries", [])
    
    print(f"Loaded {len(queries)} test queries from golden set")
    print(f"API Base URL: {API_BASE_URL}\n")
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Evaluate each query
    all_results = []
    for query_data in queries:
        result = evaluate_query(query_data)
        all_results.append(result)
    
    # Calculate overall metrics
    total_queries = len(all_results)
    successful_queries = sum(1 for r in all_results if r["status"] == "success")
    
    if successful_queries > 0:
        avg_precision = sum(r["metrics"].get("precision", 0) for r in all_results if r["status"] == "success") / successful_queries
        avg_recall = sum(r["metrics"].get("recall", 0) for r in all_results if r["status"] == "success") / successful_queries
        avg_required_recall = sum(r["metrics"].get("required_recall", 0) for r in all_results if r["status"] == "success") / successful_queries
    else:
        avg_precision = avg_recall = avg_required_recall = 0
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"eval_results_{timestamp}.json"
    
    evaluation_summary = {
        "timestamp": timestamp,
        "golden_set_version": golden_set.get("version", "unknown"),
        "api_base_url": API_BASE_URL,
        "summary": {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": total_queries - successful_queries,
            "average_precision": round(avg_precision, 3),
            "average_recall": round(avg_recall, 3),
            "average_required_recall": round(avg_required_recall, 3)
        },
        "results": all_results
    }
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_summary, f, indent=2, ensure_ascii=False)
    
    # Save latest scores
    with open(SCORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(evaluation_summary["summary"], f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 Evaluation Summary")
    print("=" * 60)
    print(f"Total Queries: {total_queries}")
    print(f"Successful: {successful_queries}")
    print(f"Failed: {total_queries - successful_queries}")
    print(f"\nAverage Precision: {avg_precision:.3f}")
    print(f"Average Recall: {avg_recall:.3f}")
    print(f"Average Required Recall: {avg_required_recall:.3f}")
    print(f"\nResults saved to: {results_file}")
    print(f"Scores saved to: {SCORES_FILE}")
    
    return evaluation_summary


if __name__ == "__main__":
    # Allow API URL override via command line
    if len(sys.argv) > 1:
        API_BASE_URL = sys.argv[1]
    
    try:
        run_evaluation()
    except KeyboardInterrupt:
        print("\n\n⚠️ Evaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

