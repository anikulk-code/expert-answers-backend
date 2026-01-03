# Setup Guide

## Prerequisites

- Python 3.8 or higher
- YouTube Data API v3 key

## Step 1: Get YouTube API Key

### 1.1. Access Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account (or create one if needed)

### 1.2. Create or Select a Project

1. Click on the project dropdown at the top of the page (next to "Google Cloud")
2. Click **"New Project"** (or select an existing project)
3. If creating new:
   - Enter project name: `expert-answers-app` (or any name you prefer)
   - Click **"Create"**
   - Wait a few seconds for the project to be created
4. Make sure your new project is selected in the dropdown

### 1.3. Enable YouTube Data API v3

1. In the left sidebar, go to **"APIs & Services"** > **"Library"**
2. In the search bar, type: `YouTube Data API v3`
3. Click on **"YouTube Data API v3"** from the results
4. Click the **"Enable"** button
5. Wait for the API to be enabled (you'll see a confirmation message)

### 1.4. Create API Key

1. In the left sidebar, go to **"APIs & Services"** > **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"API Key"** from the dropdown
4. A popup will appear with your new API key - **copy it immediately** (you won't be able to see it again!)
5. Click **"Close"** (don't restrict it yet - we'll do that next)

### 1.5. (Recommended) Restrict API Key for Security

1. In the Credentials page, find your newly created API key
2. Click on the API key name (or the edit/pencil icon)
3. Under **"API restrictions"**:
   - Select **"Restrict key"**
   - Choose **"YouTube Data API v3"** from the dropdown
4. Under **"Application restrictions"** (optional but recommended):
   - Select **"IP addresses (web servers, cron jobs, etc.)"** for production
   - Or **"None"** for development/testing
5. Click **"Save"**

**Important:** 
- Keep your API key secret - never commit it to version control
- The free tier allows 10,000 units per day (1 search = 100 units, so ~100 searches/day)
- You can monitor usage in the Google Cloud Console under "APIs & Services" > "Dashboard"

## Step 2: Set Up Virtual Environment

```bash
cd expert-answers-backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 4: Configure Environment Variables

Create a `.env` file in the root directory:

```bash
# Create .env file (if .env.example exists, copy it)
cp .env.example .env

# Or create it manually
touch .env
```

Edit `.env` and add your YouTube API key:

```env
YOUTUBE_API_KEY=your_actual_api_key_here
PORT=8000
```

**Important:** 
- Replace `your_actual_api_key_here` with the API key you copied from Google Cloud Console
- Make sure there are no quotes around the API key value
- The `.env` file should already be in `.gitignore` - verify this to avoid committing your key

### Verify .env file is ignored

Check that `.env` is in `.gitignore`:

```bash
grep -q "^\.env$" .gitignore && echo "✓ .env is in .gitignore" || echo "⚠ Add .env to .gitignore!"
```

## Step 5: Run the Server

```bash
# Development mode (with auto-reload)
uvicorn app.main:app --reload

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Step 6: Test the API

```bash
# Test the answers endpoint
curl "http://localhost:8000/api/answers?topic=Vedanta&author=Sarvapriyananda&count=5"
```

Or use the Swagger UI at http://localhost:8000/docs to test interactively.

