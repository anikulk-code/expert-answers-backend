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

### Version 2: Automatic Transcript Generation 🔄

- Automatic video parsing and transcript generation
- NLP/ML for question-answer matching, relevance scoring, viewpoint analysis

