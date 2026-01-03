# Expert Answers Backend API

Backend API for the Expert Answers application that provides answers from YouTube video segments by recognized experts.

## Features

- RESTful API for retrieving expert answers from YouTube videos
- Topic-based querying
- Support for multiple experts per topic
- YouTube API integration (Version 0)
- FastAPI framework with automatic API documentation

## Architecture

- **Separation of Concerns**: Backend exposes APIs only, no presentation logic
- **Core API**: `GetAnswers(topic, author, dateRange, count)`
- **Response Format**: JSON with video links, timestamps, speakers, and metadata

## Setup

### Prerequisites

- Python 3.8+
- YouTube Data API v3 key

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file:

```env
YOUTUBE_API_KEY=your_youtube_api_key_here
PORT=8000
```

### Running the Server

```bash
# Development
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API documentation will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Get Answers

```
GET /api/answers?topic={topic}&author={author}&dateRange={dateRange}&count={count}
```

**Parameters:**
- `topic` (required): Topic of the question
- `author` (optional): Filter by specific expert/author
- `dateRange` (optional): Date range for videos
- `count` (optional): Number of results to return (default: 10)

**Response:**
```json
[
  {
    "videoLink": "https://youtube.com/watch?v=...",
    "time": "00:15:30",
    "speakers": "Sarvapriyananda",
    "date": "2024-01-15",
    "region": "optional",
    "score": "optional",
    "answerViewPoint": "optional"
  }
]
```

## Development Roadmap

- **Version 0**: YouTube Search API integration
- **Version 1**: Q&A videos with comments-based question-answer matching
- **Version 2**: Video parsing and automatic question-answer transcript generation

