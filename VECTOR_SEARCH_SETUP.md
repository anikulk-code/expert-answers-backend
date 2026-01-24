# Azure Cosmos DB Vector Search Setup Guide

## Overview

After enabling Vector Search for NoSQL API in Azure Cosmos DB, you need to:

1. **Create/Update Container with Vector Index Policy**
2. **Update Vector Search Implementation** to use Cosmos DB's VectorDistance() function
3. **Generate Query Embeddings** for search queries
4. **Update Container Creation Code** to include vector index

## Important Notes from Azure

⚠️ **Key Limitations:**
- Vector indexes can only be applied on **new collections** at this time
- Once enabled, this capability **cannot be disabled**
- Requires latest versions of SDKs (.NET, Python, JavaScript, Java)
- **Strongly recommended** to create a vector index to reduce RU cost and latency
- Currently not supported with Shared Throughput and Analytical Store
- May take up to 15 minutes to be applied after enabling

## Step 1: Update Container with Vector Index Policy

The container needs a vector index policy. Since vector indexes can only be applied to new collections, you have two options:

### Option A: Create New Container (Recommended for Fresh Start)

If you're okay recreating the container, we'll update the code to create a new container with vector index.

### Option B: Keep Existing Container (For Now)

If you want to keep existing data, you can:
1. Keep using the existing container (vector search will work but slower without index)
2. Later migrate to a new container with vector index

## Step 2: Vector Index Configuration

For `text-embedding-3-large` (3072 dimensions), we'll use:
- **Index Type**: `flat` (good for accuracy, recommended for < 10K vectors)
- **Dimension**: `3072`
- **Path**: `/embedding`

## Step 3: Implementation Changes Needed

1. Update `cosmos_service.py` to create container with vector index policy
2. Update `search_service.py` to use VectorDistance() function
3. Add query embedding generation in vector_search()
4. Update SDK if needed (azure-cosmos should support this)

## Next Steps

After you enable Vector Search in Azure Portal:
1. Wait 15 minutes for it to be applied
2. Run the updated code to create/update container with vector index
3. Test vector search functionality
