# Guide: Recreate Cosmos DB Container with Vector Search

## Summary

The delete script (`scripts/delete_all_questions.py`) **only deletes items**, not the container itself. To fix the vector search issue, we need to:

1. Create a **new container** (`questions_v2`) with the correct vector embedding policy
2. Migrate data from the old container to the new one
3. Update the environment variable to use the new container

## Step-by-Step Instructions

### Step 1: Verify Current Container Name

Check your `.env` file:
```bash
grep COSMOS_CONTAINER_NAME .env
```

Current container is likely: `questions`

### Step 2: Create New Container with Vector Embedding Policy

Run the setup script to create a new container:

```bash
python scripts/setup_vector_index.py --new-container questions_v2
```

This will create a container named `questions_v2` with:
- ✅ Vector Embedding Policy (dimensions: 3072, dataType: float32, distanceFunction: cosine)
- ✅ Vector Index Policy (type: flat, path: /embedding)

### Step 3: Migrate Data to New Container

After creating the container, migrate your existing data:

```bash
python scripts/setup_vector_index.py --new-container questions_v2 --migrate
```

This will:
- Copy all items from `questions` → `questions_v2`
- Preserve all data including embeddings

### Step 4: Update Environment Variable

Update your `.env` file to use the new container:

```bash
# Change this line:
COSMOS_CONTAINER_NAME=questions

# To:
COSMOS_CONTAINER_NAME=questions_v2
```

### Step 5: Verify Vector Embedding Policy in Azure Portal

1. Go to Azure Portal → Your Cosmos DB Account
2. Data Explorer → `expert-answers-db` → `questions_v2`
3. Click **Settings** (gear icon)
4. Check **Vector Embedding Policy** - should show:
   ```json
   {
     "vectorEmbeddings": [
       {
         "path": "/embedding",
         "dataType": "float32",
         "dimensions": 3072,
         "distanceFunction": "cosine"
       }
     ]
   }
   ```

### Step 6: Test Vector Search

Restart your server and test with different queries. Results should now change based on the query!

```bash
# Restart server
uvicorn app.main:app --reload
```

## Troubleshooting

### If Container Creation Fails

**Error: "Vector search feature not enabled"**
- Go to Azure Portal → Cosmos DB Account → Features
- Enable "Vector Search for NoSQL API"
- Wait 15 minutes, then retry

**Error: "Parameter not recognized"**
- The SDK parameter name might be different
- Check Azure SDK version: `pip show azure-cosmos`
- Should be `>=4.7.0`

### If Migration Fails

- Check that source container exists
- Verify you have read/write permissions
- Check Azure Portal for any errors

### If Vector Search Still Doesn't Work

1. Verify Vector Embedding Policy exists in Azure Portal
2. Check that embeddings have exactly 3072 dimensions
3. Test query directly in Azure Portal Data Explorer
4. Check server logs for any errors

## What Gets Deleted?

- **`delete_all_questions.py`**: Deletes **items only**, container remains
- **Deleting container manually**: Deletes **container + all items** (irreversible!)

## Keeping Old Container

The old `questions` container will remain untouched, so you can:
- Compare results between old and new containers
- Keep it as a backup
- Delete it later once you've verified everything works

## Next Steps After Migration

1. Test vector search with different queries
2. Verify results change based on query
3. Once confirmed working, you can optionally delete the old `questions` container
4. Update any scripts/documentation that reference the container name
