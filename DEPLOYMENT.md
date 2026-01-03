# Deployment Guide

This guide covers deploying the Expert Answers Backend API to various platforms.

## Prerequisites

- YouTube API key (from Google Cloud Console)
- Git repository set up
- Account on your chosen deployment platform

## Environment Variables

Set these environment variables in your deployment platform:

- `YOUTUBE_API_KEY`: Your YouTube Data API v3 key
- `PORT`: Port number (usually set automatically by platform)
- `ALLOWED_ORIGINS`: Comma-separated list of allowed origins for CORS (optional, defaults to "*")

## Deployment Options

### Option 1: Railway (Recommended)

1. **Sign up/Login**: Go to [railway.app](https://railway.app)

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo" (or upload code)

3. **Configure Environment Variables**:
   - Go to Project Settings → Variables
   - Add `YOUTUBE_API_KEY` with your API key

4. **Deploy**:
   - Railway will automatically detect the `railway.json` file
   - The app will build and deploy automatically
   - Your API will be available at `https://your-app-name.railway.app`

### Option 2: Render

1. **Sign up/Login**: Go to [render.com](https://render.com)

2. **Create New Web Service**:
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Select the `expert-answers-backend` directory

3. **Configure**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3

4. **Set Environment Variables**:
   - Add `YOUTUBE_API_KEY` in the Environment section

5. **Deploy**:
   - Click "Create Web Service"
   - Your API will be available at `https://your-app-name.onrender.com`

### Option 3: Heroku

1. **Install Heroku CLI**: [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)

2. **Login and Create App**:
   ```bash
   heroku login
   heroku create your-app-name
   ```

3. **Set Environment Variables**:
   ```bash
   heroku config:set YOUTUBE_API_KEY=your_api_key_here
   ```

4. **Deploy**:
   ```bash
   git push heroku main
   ```

5. **Your API**: `https://your-app-name.herokuapp.com`

## Post-Deployment

1. **Test the API**:
   ```bash
   curl https://your-deployed-url.com/health
   curl "https://your-deployed-url.com/api/answers?topic=Vedanta&author=Sarvapriyananda&count=2"
   ```

2. **Update Frontend**:
   - Set `REACT_APP_API_URL` environment variable to your deployed backend URL
   - Or update the frontend code to use the deployed URL

3. **Monitor**:
   - Check logs in your deployment platform
   - Monitor API usage in Google Cloud Console

## Troubleshooting

### API Key Issues
- Verify `YOUTUBE_API_KEY` is set correctly
- Check API key restrictions in Google Cloud Console
- Ensure YouTube Data API v3 is enabled

### CORS Issues
- Set `ALLOWED_ORIGINS` environment variable with your frontend URL
- Format: `https://your-frontend.com,https://www.your-frontend.com`

### Port Issues
- Most platforms set `PORT` automatically
- Ensure your start command uses `$PORT` variable

### Build Failures
- Check Python version compatibility
- Verify all dependencies in `requirements.txt`
- Check platform-specific build logs

## Production Checklist

- [ ] Environment variables configured
- [ ] CORS origins set correctly
- [ ] API key restrictions configured in Google Cloud
- [ ] Health endpoint responding
- [ ] API endpoint returning data
- [ ] Frontend connected and working
- [ ] Monitoring/logging set up

