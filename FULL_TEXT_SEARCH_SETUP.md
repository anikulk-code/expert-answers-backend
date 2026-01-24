# Azure Cosmos DB Full Text Search Setup

## Why Use Full Text Search?

**Current Implementation (SLOW - 7+ seconds):**
- Fetches ALL ~2600 questions from Cosmos DB
- Loads all into Python memory
- Builds BM25 index in Python
- Scores all questions in Python
- Sorts all questions in Python

**With Full Text Search (FAST - <1 second):**
- Server-side indexing and search
- Only returns matching results
- BM25 scoring done in Cosmos DB
- Much faster and more efficient

## Setup Steps

### 1. Configure Full Text Policy in Azure Portal

In the Azure Portal, for your `questions` container:

1. Go to **Data Explorer** → `expert-answers-db` → `questions` → **Settings** → **Container Policies**
2. Click **Full Text Policy** tab
3. Add full-text paths:
   - **Path 1**: `/normalizedText` (Language: English (US))
   - **Path 2**: `/questionText` (Language: English (US)) 
   - **Path 3**: `/canonical_text` (Language: English (US))
4. Click **Save**

### 2. Full Text Search Query Syntax

Azure Cosmos DB Full Text Search uses the `FullTextSearch()` function:

```sql
SELECT TOP 10
    c.*,
    FullTextSearch(c.normalizedText, @query) AS score
FROM c
WHERE FullTextSearch(c.normalizedText, @query) > 0
ORDER BY FullTextSearch(c.normalizedText, @query) DESC
```

### 3. What Fields to Index

Based on your schema, you should add Full Text Policy for:
- `/normalizedText` - Primary search field
- `/questionText` - Original question text
- `/canonical_text` - Stripped-down question

**Note:** You can also add `/topics` if you want to search topics as text, but topics are better handled by the topic/entity search method.

## Performance Improvement

**Before (Client-side BM25):**
- Time: 7+ seconds
- Network: Transfers all ~2600 documents
- Processing: All in Python

**After (Full Text Search):**
- Time: <1 second (estimated)
- Network: Only matching results
- Processing: Server-side with indexes

## Implementation

The code has been updated to:
1. Try Full Text Search first (if available)
2. Fall back to client-side BM25 if Full Text Search not configured
3. Show a warning when using slow client-side method

## Testing

After configuring Full Text Policy:
1. Wait a few minutes for indexes to build
2. Test the search - should be much faster
3. Check console logs - should not see the warning message
