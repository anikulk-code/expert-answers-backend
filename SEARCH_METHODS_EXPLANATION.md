# Search Methods Explanation

## Overview
The debug page now shows **4 search methods**, each displaying **top 5 results**:

1. **Vector Results** - Semantic similarity search
2. **Topic/Entity Results** - Keyword/topic matching search  
3. **Combined Results** - Merged vector + topics results
4. **LLM Filtered Results** - Combined results filtered by LLM (what homepage uses)

---

## 1. Vector Results (Top 5)

### How it works:
- Uses **semantic similarity** via vector embeddings
- Generates an embedding for the query using OpenAI
- Searches Cosmos DB using `VectorDistance()` function
- **Sorting**: By `VectorDistance()` in **ascending order** (lower distance = more similar)
- Distance is converted to similarity score: `similarity = 1 - distance`
- Returns top 5 results with highest similarity scores

### Example:
Query: "Why should I care about spirituality?"
- Result #1: Score 0.393 (distance 0.607) - "Why is private spirituality not spirituality?"
- Result #2: Score 0.429 (distance 0.571) - "Why should I strive for enlightenment?"

---

## 2. Topic/Entity Results (Top 5)

### How it works:
- Extracts **topics and entities** from the query using LLM
- Searches Cosmos DB for questions where the `topics` array contains matching topics
- **Scoring** (only matches against `topics` array, NOT `questionText`):
  - **2.0 points** per exact topic match in the question's `topics` array
  - **1.5 points** per fuzzy topic match (e.g., "ai" matches "artificial intelligence")
  - **2.0x multiplier** if the question matches **ALL** query topics (exact or fuzzy)
- **Sorting**: By `topic_entity_score` in **descending order** (higher score = better match)
- Returns top 5 results with highest scores

**Important**: The matching is done against the stored `topics` array field, not by searching within the `questionText`. So if a question has `topics: ["spirituality", "enlightenment"]`, it will match queries with topic "spirituality" even if the word "spirituality" doesn't appear in the question text itself.

### Example:
Query: "Why should I care about spirituality?"
- Extracted topics: ["spirituality"]
- Result #1: Score 2.0 - "What should I do if I want this to be my last birth? Is God with form part of Maya?" (topics: ["birth", "spirituality"])
- Result #2: Score 2.0 - "In the Mahabharata it is said..." (topics: ["dharma", "spirituality"])

---

## 3. Combined Results (Top 5)

### How it works:
- Runs **both** vector search (top 5) and topics search (top 5)
- **Merges** results by question ID (deduplicates)
- **Combined Score**: Uses `max(vector_score, topic_entity_score)`
  - If a question appears in both lists, it gets the higher of the two scores
  - If it only appears in one list, it uses that score
- **Sorting**: By `combined_score` in **descending order** (highest first)
- Returns top 5 results

### Example:
Query: "Why should I care about spirituality?"
- Vector result #1: "Why is private spirituality not spirituality?" (vector_score: 0.393)
- Topics result #1: "What should I do if I want this to be my last birth?" (topic_score: 2.0)
- **Combined result #1**: "What should I do if I want this to be my last birth?" (combined_score: 2.0) ← Higher score wins
- **Combined result #2**: "Why is private spirituality not spirituality?" (combined_score: 0.393)

**Note**: Items that appear in **both** lists will have both scores, but the combined score uses the maximum. This means questions that match both semantically AND by topic will rank highly.

---

## 4. LLM Filtered Results (Top 5)

### How it works:
- Runs **both** vector search (top 50) and topics search (top 50)
- Merges and deduplicates (same as Combined)
- Sends the **combined list** (up to 100 unique questions) to GPT-4o
- LLM filters for **relevance** to the user's query
- Returns top 5 most relevant questions (as determined by LLM)

### LLM Filtering Criteria:
- Questions that directly answer the user's question
- Questions that address the same core topic/concept
- Questions that explore related aspects
- Excludes: gibberish, completely unrelated questions

### Example:
Query: "Why should I care about spirituality?"
- Combined list: 100 questions (from vector + topics)
- LLM filters to: 5 most relevant questions
- Result #1: "Why is private spirituality not spirituality?" (LLM selected as most relevant)
- Result #2: "What should I do if I want this to be my last birth?" (LLM selected)

**This is what the homepage uses** - it's the final, LLM-filtered version of the combined search.

---

## Key Differences

| Method | Sorting | Score Range | Shows Items In Both Lists? |
|--------|---------|-------------|---------------------------|
| Vector | By similarity (ascending distance) | 0.0 - 1.0 | N/A (single method) |
| Topics | By topic match score (descending) | 0.0 - 4.0+ | N/A (single method) |
| Combined | By max(vector, topics) score (descending) | 0.0 - 4.0+ | ✅ Yes, uses max score |
| LLM Filtered | By LLM relevance judgment | N/A | ✅ Yes, then LLM filters |

---

## Why Combined Results Might Show Different Order

The combined results don't simply show "items that appear at the top of both lists first". Instead:

1. **Merges** both lists by ID
2. **Assigns combined_score = max(vector_score, topic_entity_score)**
3. **Sorts by combined_score** (highest first)

So if:
- Vector #1 has score 0.5
- Topics #1 has score 2.0
- Topics #2 has score 1.5

The combined results will be:
- #1: Topics #1 (score 2.0)
- #2: Topics #2 (score 1.5)  
- #3: Vector #1 (score 0.5)

Items that appear in **both** lists will have both scores, and the max is used. This means a question with vector_score=0.4 and topic_score=2.0 will have combined_score=2.0 and rank high.
