# Evaluation System

This directory contains the golden evaluation set for testing the Expert Answers API.

## Structure

- `golden_set.json` - Test queries with expected results
- `results/` - Directory for storing actual API results (gitignored)
- `scores.json` - Evaluation scores (gitignored)

## Golden Set Format

Each query in `golden_set.json` has:
- `id`: Unique identifier
- `query`: The test question
- `description`: What this test is checking
- `expected_answers`: List of answers that should be returned
  - `question`: Expected question text (exact or partial match)
  - `url_pattern`: Pattern to match in URL (e.g., "youtube.com")
  - `min_rank`: Minimum expected rank (1 = first result)
  - `required`: Whether this answer must be present
- `min_relevant_count`: Minimum number of relevant results expected
- `max_results_to_check`: How many results to evaluate

## How to Populate

1. Run your API with each query
2. Identify which results are actually relevant
3. Add those to `expected_answers` in the golden set
4. Mark `required: true` for must-have answers, `false` for nice-to-have

## Next Steps

After creating the golden set, we'll create an evaluation script that:
1. Runs each query against the API
2. Compares results with expected answers
3. Calculates precision, recall, and ranking metrics
4. Generates a report

