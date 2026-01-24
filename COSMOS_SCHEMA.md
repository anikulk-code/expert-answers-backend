# Cosmos DB Schema Documentation

## Question Document Schema

Each question document in Cosmos DB follows this schema, aligned with the reference design:

### Core Fields

- **`id`** (string): Unique identifier (UUID)
- **`domain`** (string): Coarse area classification
  - Examples: `"philosophy"`, `"technology"`, `"medicine"`, `"finance"`
  - Default: `"philosophy"` for Vedanta questions

- **`questionText`** (string): Original question text
- **`normalizedText`** (string): Lowercase, trimmed version for case-insensitive matching
- **`canonical_text`** (string): Stripped down version of question to bare minimum (computed by LLM)
  - Example: `"What is the vedantic view of evolution?"` → `"vedantic view evolution"`

### Vector Search Fields

- **`embedding`** (array of floats, optional): Vector embedding for semantic search
- **`embeddingModel`** (string, optional): Model used for embedding
  - Example: `"text-embedding-3-large"`
- **`embeddingDim`** (integer, optional): Dimension of embedding vector
  - Example: `3072` for text-embedding-3-large

### Classification Fields

- **`topics`** (array of strings): General subject areas or themes (computed by LLM)
  - Example: `["evolution", "vedanta", "consciousness"]`
  - Used for categorization and filtering

- **`entities`** (array of objects): Specific named things with types (computed by LLM)
  - Each entity has:
    - **`type`** (string): One of `"person"`, `"concept"`, `"place"`, `"text"`
    - **`name`** (string): Name of the entity
  - Example: `[{"type": "person", "name": "Buddha"}, {"type": "concept", "name": "Advaita"}]`

- **`tags`** (array of strings, optional): Broader/UI-facing tags
  - Example: `["indian_philosophy", "religion"]`
  - Separate from topics - used for UI display and broader categorization

### Video Links (Application-Specific)

- **`video_link`** (string, optional): Link to specific video segment with timestamp
  - Example: `https://www.youtube.com/watch?v=VIDEO_ID&t=1234s`
- **`full_video_link`** (string, optional): Link to full video without timestamp
  - Example: `https://www.youtube.com/watch?v=VIDEO_ID`
- **`playlist_link`** (string, optional): Link to playlist containing the video
  - Example: `https://www.youtube.com/playlist?list=PLAYLIST_ID`

### Engagement Fields

- **`voteUp`** (integer): Number of upvotes (default: 0)
- **`timesAsked`** (integer): Count of how many times the question was asked (default: 1)
- **`status`** (string): Question status
  - Values: `"active"` | `"hidden"` | `"archived"`
  - Default: `"active"`

### Timestamps

- **`createdAt`** (string): ISO 8601 timestamp when question was created
- **`updatedAt`** (string): ISO 8601 timestamp when question was last updated

## Example Document

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "domain": "philosophy",
  "questionText": "What is the vedantic view of evolution?",
  "normalizedText": "what is the vedantic view of evolution?",
  "canonical_text": "vedantic view evolution",
  "topics": ["evolution", "vedanta"],
  "entities": [],
  "tags": ["indian_philosophy", "religion"],
  "video_link": "https://www.youtube.com/watch?v=VIDEO_ID&t=1234s",
  "full_video_link": "https://www.youtube.com/watch?v=VIDEO_ID",
  "playlist_link": "https://www.youtube.com/playlist?list=PLAYLIST_ID",
  "embedding": [0.0123, -0.9812, ...],
  "embeddingModel": "text-embedding-3-large",
  "embeddingDim": 3072,
  "voteUp": 5,
  "timesAsked": 18,
  "status": "active",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T10:30:00.000Z"
}
```

## Backward Compatibility

The schema supports backward compatibility with older documents that may have:
- `question` instead of `questionText`
- `question_normalized` instead of `normalizedText`
- `votes` or `upvotes` instead of `voteUp`
- `created_at`/`updated_at` instead of `createdAt`/`updatedAt`
- Missing computed fields (`canonical_text`, `topics`, `entities`)
- Missing new fields (`domain`, `tags`, `embedding`, `timesAsked`, `status`)

All queries and functions handle both old and new schema formats.

## Field Naming

The schema uses **camelCase** for new fields to match the reference design:
- `questionText`, `normalizedText`, `voteUp`, `timesAsked`, `createdAt`, `updatedAt`, `embeddingModel`, `embeddingDim`

Legacy fields use **snake_case** for backward compatibility:
- `question`, `question_normalized`, `votes`, `created_at`, `updated_at`

## Vector Search Ready

This schema is designed to work with Azure Cosmos DB's vector search capabilities:
- `embedding`: Store vector embeddings
- `embeddingModel`: Track which model was used
- `embeddingDim`: Store dimension for validation
- `canonical_text`, `topics`, `entities`: Used for hybrid search (vector + keyword)
- `domain`, `tags`: Used for filtering and categorization
