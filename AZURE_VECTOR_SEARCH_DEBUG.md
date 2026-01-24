# Azure Cosmos DB Vector Search Configuration Debug Guide

## Problem Summary

Vector search is returning the same results regardless of query, even though:
- ✅ Different query embeddings are generated correctly
- ✅ Different distances are calculated
- ✅ Parameters are passed correctly to Cosmos DB
- ❌ Same result ID appears first for all queries

This suggests Cosmos DB's `VectorDistance()` function may not be using the `@queryVector` parameter correctly.

## Step 1: Check Vector Index Configuration in Azure Portal

### 1.1 Navigate to Your Cosmos DB Account

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Cosmos DB account
3. Go to **Data Explorer** → Select your database → Select your container

### 1.2 Check Container Policies (CRITICAL!)

Cosmos DB requires **TWO separate policies** for vector search:

#### A. Vector Embedding Policy (MOST LIKELY MISSING!)

1. Click on **Settings** (gear icon) next to your container
2. Click on **Vector Embedding Policy**
3. **This MUST exist and specify dimensions:**

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

**⚠️ CRITICAL:** If this policy is missing or doesn't specify `dimensions: 3072`, vector search will NOT work correctly!

#### B. Indexing Policy with Vector Indexes

1. Click on **Indexing Policy**
2. Look for `vectorIndexes` section:

```json
{
  "indexingMode": "consistent",
  "automatic": true,
  "includedPaths": [
    {
      "path": "/*"
    }
  ],
  "vectorIndexes": [
    {
      "path": "/embedding",
      "type": "flat"
    }
  ]
}
```

**Note:** The dimension is specified in Vector Embedding Policy, NOT in vectorIndexes.

### 1.3 Verify Vector Search is Enabled

1. In Azure Portal, go to your Cosmos DB account
2. Click on **Features** in the left menu
3. Look for **Vector Search** - it should be **Enabled**

**Note:** Vector Search must be enabled at the account level before it can be used.

## Step 2: Test Query Directly in Azure Portal

### 2.1 Use Data Explorer Query

1. In Azure Portal → Data Explorer → Your Container
2. Click on **New SQL Query**
3. Test with a hardcoded vector:

```sql
SELECT TOP 5
    c.id,
    c.questionText,
    VectorDistance(c.embedding, [0.007880894467234612, -0.027427539229393005, -0.025936754420399666], true) AS vector_distance
FROM c
WHERE IS_ARRAY(c.embedding) = true
    AND ARRAY_LENGTH(c.embedding) = 3072
ORDER BY vector_distance
```

**Note:** Use only the first 3 values for testing (you'll need to truncate or use a smaller test vector).

### 2.2 Test with Parameter

Try using a parameter in Azure Portal:

```sql
SELECT TOP 5
    c.id,
    c.questionText,
    VectorDistance(c.embedding, @queryVector, @useExactSearch) AS vector_distance
FROM c
WHERE IS_ARRAY(c.embedding) = true
    AND ARRAY_LENGTH(c.embedding) = @embedding_dim
ORDER BY vector_distance
```

**Parameters:**
- `@queryVector`: `[0.007880894467234612, -0.027427539229393005, -0.025936754420399666, ...]` (full 3072-dim vector)
- `@useExactSearch`: `true`
- `@embedding_dim`: `3072`

**Check:** Do you get different results when you change the `@queryVector` parameter?

## Step 3: Check SDK Version Compatibility

### 3.1 Verify SDK Version

Check your `requirements.txt`:
```bash
cat requirements.txt | grep azure-cosmos
```

**Required:** `azure-cosmos>=4.7.0` (for VectorDistance support)

### 3.2 Check Python SDK Documentation

Verify that your SDK version supports `VectorDistance()` with array parameters:
- [Azure Cosmos DB Python SDK Vector Search Docs](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/vector-search)

## Step 4: Verify Container Was Created with Vector Index

### 4.1 Check Container Creation Script

Review `scripts/setup_vector_index.py` - the vector index configuration should include:

```python
vector_index_policy = {
    "vectorIndexes": [
        {
            "path": "/embedding",
            "type": "flat",
            # NOTE: Dimension might need to be specified here!
        }
    ]
}
```

### 4.2 Check if Container Has Vector Index

Run this query to check container metadata:

```python
from app.services.cosmos_service import get_cosmos_container

container = get_cosmos_container()
container_properties = container.read()

print("Indexing Policy:")
import json
print(json.dumps(container_properties.get('indexingPolicy', {}), indent=2))
```

Look for `vectorIndexes` in the output.

## Step 5: Known Issues and Workarounds

### Issue 1: Vector Index Missing Dimension

**Symptom:** Vector search returns same results
**Fix:** Update indexing policy to include dimension:

```json
{
  "vectorIndexes": [
    {
      "path": "/embedding",
      "type": "flat",
      "dimension": 3072
    }
  ]
}
```

**Note:** This might require recreating the container (vector indexes can only be added to new containers).

### Issue 2: SDK Not Serializing Array Parameters Correctly

**Symptom:** Parameters are passed but Cosmos DB ignores them
**Workaround:** Try inlining the vector directly in the query (we already tried this, but it might work with a different format)

### Issue 3: Vector Index Not Fully Built

**Symptom:** Queries work but return incorrect results
**Fix:** Wait 15+ minutes after enabling vector search, or rebuild the index

## Step 6: Diagnostic Queries

### 6.1 Check Stored Embeddings Are Different

```sql
SELECT TOP 3
    c.id,
    c.questionText,
    c.embedding[0] AS first_embedding_value,
    c.embedding[1] AS second_embedding_value,
    c.embedding[2] AS third_embedding_value
FROM c
WHERE IS_ARRAY(c.embedding) = true
    AND ARRAY_LENGTH(c.embedding) = 3072
```

**Expected:** Different questions should have different embedding values.

### 6.2 Check Vector Index Status

```sql
SELECT 
    c.id,
    c.questionText,
    IS_ARRAY(c.embedding) AS has_embedding,
    ARRAY_LENGTH(c.embedding) AS embedding_length
FROM c
WHERE IS_ARRAY(c.embedding) = true
LIMIT 10
```

## Step 7: Next Steps Based on Findings

### If Vector Index is Missing Dimension:

1. **Option A:** Recreate container with correct index (requires data migration)
   ```bash
   python scripts/setup_vector_index.py --new-container questions_v2 --migrate
   ```

2. **Option B:** Contact Azure Support to add dimension to existing index

### If SDK Issue:

1. Try updating to latest SDK:
   ```bash
   pip install --upgrade azure-cosmos
   ```

2. File a bug report with Microsoft Azure Support

### If Vector Search Not Enabled:

1. Enable Vector Search in Azure Portal:
   - Account → Features → Vector Search → Enable
   - Wait 15 minutes for propagation

## Step 8: Alternative Workaround (If Azure Issue)

If Cosmos DB's `VectorDistance()` continues to ignore parameters, we can:

1. **Client-side vector similarity:** Fetch top N results, calculate cosine similarity in Python
2. **Use a different vector database:** Migrate to Azure AI Search, Pinecone, or Weaviate
3. **Hybrid approach:** Use Cosmos DB for storage, calculate similarity in application layer

## Quick Checklist

- [ ] Vector Search enabled at account level
- [ ] Container has vector index with correct path (`/embedding`)
- [ ] Vector index specifies dimension (`3072`)
- [ ] SDK version is `>=4.7.0`
- [ ] Test query in Azure Portal with different vectors returns different results
- [ ] Stored embeddings are actually different (check first 3 values)
- [ ] Container was created AFTER Vector Search was enabled

## Contact Points

- **Azure Support:** If configuration looks correct but still not working
- **GitHub Issues:** [azure-sdk-for-python](https://github.com/Azure/azure-sdk-for-python/issues) - for SDK bugs
- **Azure Docs:** [Vector Search Documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/vector-search)
