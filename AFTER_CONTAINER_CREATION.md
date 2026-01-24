# Quick Start Guide: After Container Creation

## ✅ Container Created Successfully!

You've created the `questions` container with:
- ✅ Vector Embedding Policy: `/embedding` (3072 dims, cosine, quantizedFlat)
- ✅ Full Text Search: `/questionText` and `/topics` (English US)

## Next Steps

### Step 1: Verify Container Configuration

In Azure Portal, verify:
1. Container `questions` exists
2. Settings → Vector Embedding Policy shows:
   - Path: `/embedding`
   - Dimensions: `3072`
   - Distance function: `cosine`
3. Settings → Full Text Search Policy shows:
   - Paths: `/questionText` and `/topics`
   - Language: `English (US)`

### Step 2: Add Data to Container

You have two options:

#### Option A: Migrate Existing Data (if you have a JSON file)

```bash
# Migrate questions from JSON file
python scripts/migrate_questions_to_cosmos.py --questions-file askswami_questions.json

# Or with options:
python scripts/migrate_questions_to_cosmos.py \
    --questions-file askswami_questions.json \
    --skip-existing \
    --batch-size 10
```

#### Option B: Add Embeddings to Existing Questions

If you already have questions in the container but need to add embeddings:

```bash
# Add embeddings to all questions
python scripts/add_embeddings_to_questions.py
```

### Step 3: Test Vector Search

Start your server and test:

```bash
# Start server
uvicorn app.main:app --reload

# Test vector search endpoint
curl "http://localhost:8000/api/search/vector?query=What%20is%20vedantic%20view%20of%20evolution%3F&top_n=10"
```

### Step 4: Verify Vector Search Works Correctly

Test with different queries and verify:
- ✅ Results change based on the query
- ✅ Different queries return different top results
- ✅ Distances are calculated correctly

## Troubleshooting

### If Vector Search Still Returns Same Results

1. **Check Vector Embedding Policy in Azure Portal**
   - Must show dimensions: `3072`
   - Must show path: `/embedding`

2. **Verify Embeddings Exist**
   ```bash
   # Check if questions have embeddings
   python3 -c "
   import sys
   sys.path.insert(0, '.')
   from app.services.cosmos_service import get_cosmos_container
   container = get_cosmos_container()
   query = 'SELECT TOP 3 c.id, c.questionText, ARRAY_LENGTH(c.embedding) as emb_len FROM c WHERE IS_ARRAY(c.embedding) = true'
   items = list(container.query_items(query=query, enable_cross_partition_query=True))
   print(f'Found {len(items)} questions with embeddings')
   for item in items:
       print(f\"  - {item.get('questionText', 'N/A')[:50]}... (embedding length: {item.get('emb_len', 0)})\")
   "
   ```

3. **Check Container Name**
   ```bash
   # Verify container name matches
   grep COSMOS_CONTAINER_NAME .env
   # Should show: AZURE_COSMOS_CONTAINER_NAME=questions
   ```

## Expected Behavior

After fixing the Vector Embedding Policy, you should see:
- ✅ Different queries return different results
- ✅ Top result ID changes with different queries
- ✅ Vector distances vary appropriately
- ✅ Results are semantically relevant to the query

## Migration Script Options

```bash
# See all options
python scripts/migrate_questions_to_cosmos.py --help

# Common options:
--questions-file PATH    # Path to JSON file (default: askswami_questions.json)
--skip-existing         # Skip questions that already exist (default: True)
--limit N               # Limit to first N questions (for testing)
--batch-size N          # Progress update frequency (default: 10)
--dry-run               # Preview without making changes
```

## Add Embeddings Script Options

```bash
# See all options
python scripts/add_embeddings_to_questions.py --help

# Common options:
--limit N               # Limit to first N questions (for testing)
--batch-size N          # Process N questions at a time (default: 10)
```
