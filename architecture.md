# Architecture: Expert Answers from YouTube Videos

## Goal

Build an app that allows users to ask questions, where answers are specific segments of YouTube videos by recognized experts.

## Core Concepts

### Topics

- Topics are a key dimension of the application
- Must be defined upfront
- All questions and answers are scoped within a topic
- Examples: Vedanta, Artificial Intelligence (AI), Mental Health, Diet

### Experts

- Users can choose answers from one expert only, or from multiple experts
- When multiple experts are selected, users can specify whether they want:
  - **Completely different viewpoints** on the same question
  - **Multiple experts saying essentially the same thing**

## Architecture Principles

**Separation of Concerns:**
- Backend and frontend must be completely separate
- Backend exposes APIs only
- Frontend consumes APIs and handles presentation

**Security Model:**
- **Backend**: Uses YouTube API key securely (stored in `.env`, never exposed)
- **Frontend**: Does NOT use YouTube API key directly
- **Flow**: Frontend → Backend API → YouTube API
  - Frontend makes requests to backend (no authentication needed for public API)
  - Backend uses YouTube API key to fetch data from YouTube
  - This protects the API key from being exposed in client-side code

## Backend Design

### Core API

**Endpoint:** `GetAnswers(topic, author, dateRange, count)`

**Parameters:**
- `topic` (required): The topic/question area
- `author` (optional): Filter by specific expert/author
- `dateRange` (optional): Filter videos by publication date range
- `count` (optional): Number of results to return

### Response Structure

```json
{
  "videoLink": "URL to YouTube video",
  "time": "Timestamp (HH:MM:SS)",
  "speakers": "Person(s) speaking",
  "date": "Publication date (YYYY-MM-DD)",
  "region": "Optional: Geographic/cultural context",
  "score": "Optional: Relevance score",
  "answerViewPoint": "Optional: Same/different viewpoints indicator"
}
```

## Phased Implementation

### Version 0: YouTube Search API Integration ✅

- YouTube Search API integration
- Filter by topic, author, date range
- **Timestamp extraction:** Parses timestamps from video descriptions (HH:MM:SS or MM:SS format)
- **Region detection:** Infers region from channel country code or channel title keywords
- **Limitations:** Score and answerViewPoint not implemented (planned for Version 2)

### Version 1: Q&A Videos with Comments-Based Matching 🔄

- Focus on Q&A videos
- Extract timestamps from comments/descriptions
- Match questions to video segments
- **Hybrid Search**: Vector search + BM25 (keyword) search with query expansion
- **LLM Verification**: Relevance ranking and confidence scoring

#### Search Flow and Fallback Mechanisms

**Primary Search:**
1. User enters their own question
2. System performs hybrid search (vector + BM25) with expanded terms
3. LLM verifies and ranks results by relevance
4. Returns matching Q&A segments with timestamps

**Fallback When No Direct Answer Found:**
1. **Related YouTube Lectures**: Show 2-3 full YouTube lectures that could be related to the core terms extracted from the user's query
   - Uses core terms and synonyms to find relevant full-length videos
   - Provides broader context when specific Q&A segments aren't available

2. **Related Tags**: Show tags related to the core terms for exploration
   - Allows users to browse questions by topic/tag
   - Helps users discover related content through topic-based navigation

3. **Related Questions & User Engagement**:
   - Display related questions that users can explore
   - Allow users to upvote related questions (indicates interest/helpfulness)
   - If no related question exists, allow users to submit their own question
   - **Note**: Upvoting and question submission require a database (to be implemented in a future version)

### Version 2: Automatic Transcript Generation 🔄

- Automatic video parsing and transcript generation
- NLP/ML for question-answer matching, relevance scoring, viewpoint analysis

### Version 3: User Engagement & Database 🔄

- Database for storing:
  - User-submitted questions
  - Question upvotes/engagement metrics
  - User preferences and search history
- Analytics and insights from user interactions

