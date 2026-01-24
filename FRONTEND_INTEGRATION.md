# Frontend Integration Guide

## Overview

The `frontend_example.html` file provides a complete, ready-to-use frontend that integrates with the Expert Answers API, including:

- ✅ Question search with progress indicators
- ✅ Display of Q&A matches and YouTube video fallbacks
- ✅ Tag suggestions
- ✅ Question queue integration
- ✅ Upvote functionality
- ✅ Add questions to queue

## Quick Start

### 1. Update API URL

Open `frontend_example.html` and update the `API_BASE_URL` constant:

```javascript
// For local development:
const API_BASE_URL = 'http://localhost:8000/api';

// For production:
const API_BASE_URL = 'https://your-api-domain.com/api';
```

### 2. Open in Browser

Simply open `frontend_example.html` in your web browser. No build step required!

### 3. Test the Integration

1. **Search for a question**: Enter a question and click "Get Answers"
2. **View results**: See Q&A matches, YouTube videos, or tag suggestions
3. **Upvote questions**: Click the 👍 button on similar questions
4. **Add to queue**: Submit your own question to the queue

## Features

### Search Flow

The frontend handles the complete search flow:

1. **Q&A Database Search**: Searches the Q&A database first
2. **YouTube Fallback**: If no matches, searches YouTube videos
3. **Tags & Queue Fallback**: If no videos, shows tags and queue options

### Progress Indicators

The UI shows clear progress indicators:
- "Searching for questions in Q&A database..."
- "Searching for related videos..."
- "Checking video relevance..."
- "Search complete!"

### Queue Integration

- **View similar questions**: See questions similar to yours
- **Upvote questions**: Support questions you want answered
- **Add your question**: Submit questions to the queue

## API Endpoints Used

The frontend uses these API endpoints:

- `GET /api/answers/v1?question=...` - Search for answers
- `POST /api/questions/queue` - Add question to queue
- `POST /api/questions/upvote` - Upvote a question

## Customization

### Styling

The HTML file includes all CSS inline. You can customize:
- Colors: Update the CSS variables in the `<style>` section
- Layout: Modify the container and card styles
- Typography: Change font families and sizes

### Functionality

All JavaScript is in the `<script>` section. You can:
- Add new features
- Modify the UI flow
- Integrate with other services
- Add analytics tracking

## Security Notes

- ✅ XSS protection: All user input is properly escaped
- ✅ CORS: Backend must allow your frontend's origin
- ✅ API keys: Never expose API keys in frontend code

## Production Deployment

For production:

1. **Update API URL** to your production API endpoint
2. **Enable HTTPS** for secure connections
3. **Configure CORS** on the backend to allow your domain
4. **Minify CSS/JS** for better performance (optional)
5. **Add error tracking** (e.g., Sentry) for monitoring

## Troubleshooting

### CORS Errors

If you see CORS errors, ensure your backend has:
```python
# In app/main.py
allowed_origins = ["https://your-frontend-domain.com"]
```

### API Connection Issues

- Check that the API server is running
- Verify the `API_BASE_URL` is correct
- Check browser console for detailed error messages

### Questions Not Appearing

- Verify Cosmos DB is configured correctly
- Check backend logs for errors
- Ensure environment variables are set

## Next Steps

1. **Customize the UI** to match your brand
2. **Add authentication** if needed
3. **Implement caching** for better performance
4. **Add analytics** to track usage
5. **Deploy** to your hosting platform
