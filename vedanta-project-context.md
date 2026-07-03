# Expert Answers — Vedanta

Structured project context for future threads, planning, implementation, and review.

## One-line product summary

Expert Answers helps users ask natural-language spiritual questions and receive trustworthy, timestamped pointers into Swami Sarvapriyananda Q&A videos, rather than generic web-search summaries.

## Deployment scope

This deployment is the Vedanta / Swami Sarvapriyananda experience.

Current UI behavior is effectively single-expert, even though broader multi-expert ideas exist in the long-term vision.

## Repositories

- Backend: `expert-answers-backend`
  - Python FastAPI
  - Azure Cosmos DB for questions, topics, embeddings, queue/upvotes
  - Vector search plus topic/entity search
  - OpenAI for matching, filtering, and related behavior
  - YouTube Data API for thumbnails and some legacy helpers
- Frontend: `expert-answers-vedanta-frontend`
  - React
  - Main tabs: Search and Explore by Topic
  - Optional Debug tab only when `REACT_APP_ENABLE_DEBUG=true`
  - API base from `REACT_APP_API_URL`, otherwise falls back to the deployed Azure API URL

## Product goal

Deliver specific, trustworthy video segments from recognized experts.

The product should point users to the right timestamp in the right Q&A video, not synthesize a generic answer from the web.

## What is shipped today

### Main answer flow

User asks a natural-language question.

The frontend calls:

`GET /api/answers/v1?question=...&count=...`

The API returns JSON containing:

- `answers`
- optional `queueInfo`
- optional `userMessage`

Answer objects follow the `AnswerResponse` shape and may include:

- `videoLink`
- `time`
- `speakers`
- `date`
- `thumbnail`
- `questionTitle`
- `playlistId`

### Search semantics

- Primary retrieval uses the curated Q&A database.
- Main answer matches prefer items that have a `video_link`.
- Related-question and upvote-oriented paths may include questions without videos where that split is relevant.

### No-match behavior

There is no current-product fallback that searches YouTube for a random or approximate video.

If there is no strong Q&A hit, the product should move the user toward:

- related questions
- queue / upvote behavior
- explicit low-confidence or no-answer messaging

It should not pretend it found a valid answer when it did not.

### Explore by Topic

Topic browsing is supported through:

- `GET /api/tags`
- `GET /api/tags/{tag}/questions`
- `GET /api/tags/search`

Tags are driven by Cosmos/topic logic. A static JSON file is not the runtime source of truth.

### Thumbnails

Thumbnails are often loaded progressively in the Explore UI via:

`GET /api/thumbnails/{video_id}`

This keeps list endpoints fast and reduces unnecessary YouTube API pressure from the server side.

### Caching

Pre-canned questions are defined in:

`app/services/llm_service.py`

Specifically:

`PRECANNED_QUESTIONS`

These questions receive in-memory caching for expensive matching work.

The full answer response is also cached in:

`app/routers/answers.py`

This supports fast, idempotent repeat requests.

### Header/source link

The frontend header includes a Source link to the AskSwami playlist:

`AskSwami Q&A | Swami Sarvapriyananda`

## Core product principles

- Trustworthiness is more important than coverage.
- Prefer clear low-confidence or no-answer behavior over a bad match that sounds confident.
- The primary interaction is "ask anything," not "pick a topic first."
- Topics are important for browsing and exploration, but secondary to the ask flow.
- Timestamped source material is the product, not generated summaries.

## Current mental model of the system

### Backend responsibilities

- Receive natural-language questions
- Retrieve likely matches from the Q&A corpus
- Rank or filter using vector/topic/entity logic plus LLM-assisted behavior
- Return answer objects with video metadata and timestamps
- Support related-question and queue/upvote flows
- Serve topic browsing endpoints
- Serve thumbnails on demand

### Frontend responsibilities

- Search experience for asking questions
- Explore-by-topic browsing experience
- Optional debug surface behind env flag
- Progressive loading of thumbnails where appropriate
- Source link back to the AskSwami playlist

## Important non-goals for current-state discussions

Do not describe the following as part of the live core product unless a specific implementation is confirmed:

- generic YouTube search fallback as the normal no-match path
- static JSON as the source of truth for topics
- multi-expert comparison or viewpoint selection
- fully automated transcript parsing pipeline

## Ops and deployment notes

- Cosmos firewall/networking matters in production. Azure-hosted API access to Cosmos must be correctly allowed, otherwise production can fail even when local development works.
- Frontend CI can fail on ESLint warnings when `CI=true`, so warnings should be treated seriously in PR checks.

## Roadmap framing

Use this language when discussing roadmap versus shipped behavior.

### Historical / legacy

- v0-style YouTube Search exploration may exist historically or in utilities.
- It is not the core product path today.

### Current product phase

- v1 is the curated Q&A plus matching system.
- Runtime source of truth is Cosmos DB.
- Ingestion scripts or JSON files may still exist under `ManualScripts` or data folders, but they are not the runtime authority.

### Future

- v2 automatic transcript/parse pipeline is future work.
- Richer scoring, multi-expert selection, and same-vs-different-viewpoint experiences are future product dimensions.

## Recommended short context prompt for future threads

Use the following when you want a concise but accurate project setup summary:

> Expert Answers is a product that answers user questions by returning trustworthy, timestamped segments from expert YouTube Q&A videos rather than generic generated summaries. This deployment is the Vedanta / Swami Sarvapriyananda experience. The backend is a FastAPI service backed by Azure Cosmos DB for questions, topics, embeddings, and queue/upvotes, with vector/topic/entity search plus OpenAI-assisted matching/filtering. The frontend is a React app with Search and Explore by Topic tabs, plus an optional Debug tab behind `REACT_APP_ENABLE_DEBUG=true`. The main shipped flow is `GET /api/answers/v1?question=...&count=...`, which returns answer objects such as `videoLink`, `time`, `speakers`, `date`, optional `thumbnail`, `questionTitle`, and `playlistId`, plus optional `queueInfo` and `userMessage`. Primary retrieval uses the curated Q&A database and prefers items with video links. If there is no strong match, the product should favor low-confidence messaging and related-question/queue-upvote UX, not a generic YouTube fallback. Topic browsing uses `/api/tags`, `/api/tags/{tag}/questions`, and `/api/tags/search`, with Cosmos/topic logic as the source of truth. Thumbnails are often fetched progressively via `/api/thumbnails/{video_id}`. Pre-canned questions in `app/services/llm_service.py` and response caching in `app/routers/answers.py` are important performance details. Do not describe historical YouTube-search behavior, multi-expert comparison, or automatic transcript parsing as shipped unless implementation is confirmed.

## Recommended working rules for future collaborators

- Distinguish clearly between shipped behavior, legacy utilities, and roadmap.
- When in doubt, optimize for answer quality and trust rather than answer coverage.
- Preserve the no-fake-confidence principle.
- Treat Cosmos as the runtime source of truth unless a task explicitly concerns ingestion or migration.
- Assume the product is single-expert Vedanta unless the task explicitly expands scope.
