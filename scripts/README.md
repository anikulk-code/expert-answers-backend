# Migration Scripts

## migrate_questions_to_cosmos.py

Migrates questions from `askswami_questions.json` to Cosmos DB with the new schema.

### Usage

```bash
# Dry run (test without writing to Cosmos DB)
python scripts/migrate_questions_to_cosmos.py --dry-run

# Migrate all questions
python scripts/migrate_questions_to_cosmos.py

# Migrate first 10 questions (for testing)
python scripts/migrate_questions_to_cosmos.py --limit 10

# Custom questions file
python scripts/migrate_questions_to_cosmos.py --questions-file path/to/questions.json
```

### Options

- `--dry-run`: Run without actually writing to Cosmos DB (recommended first)
- `--limit N`: Only process first N questions (useful for testing)
- `--batch-size N`: Show progress every N questions (default: 10)
- `--questions-file PATH`: Path to questions JSON file (default: askswami_questions.json)

### What it does

1. Loads questions from `askswami_questions.json`
2. For each question:
   - Checks if it already exists in Cosmos DB (skips if found)
   - Extracts video links (with and without timestamp)
   - Gets playlist link if available
   - Computes `canonical_text`, `topics`, and `entities` using LLM
   - Stores in Cosmos DB with new schema
3. Provides progress updates and summary statistics

### Requirements

- Cosmos DB connection configured in `.env`
- OpenAI API key for computing canonical_text, topics, and entities
- YouTube API key (optional, for playlist lookup)

### Example Output

```
Loading questions from askswami_questions.json...
Found 2597 questions

✓ Connected to Cosmos DB

Starting migration...

[1/2597] Processing: Does Indian philosophy have a position on AI?...
  ✓ Added to Cosmos DB (ID: 550e8400...)
[10/2597] Processing: Who is experiencing qualia?...
  ✓ Added to Cosmos DB (ID: 6f3a2b1c...)
...

============================================================
MIGRATION SUMMARY
============================================================
Total questions processed: 2597
✓ Successfully migrated: 2597
⊘ Skipped (already exist): 0
✗ Errors: 0
⏱️  Time elapsed: 1245.67 seconds
⚡ Average time per question: 0.48 seconds

✅ Migration complete! 2597 questions stored in Cosmos DB
```
