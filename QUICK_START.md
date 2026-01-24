# Quick Start Guide - Azure Cosmos DB Setup

## Step 1: Get Your Cosmos DB Credentials

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Cosmos DB account
3. Click on **"Keys"** in the left menu
4. Copy the following:
   - **URI** → This is your `AZURE_COSMOS_ENDPOINT`
   - **PRIMARY KEY** → This is your `AZURE_COSMOS_KEY`

## Step 2: Configure Environment Variables

Create or update your `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Then edit `.env` and add your Cosmos DB credentials:

```env
AZURE_COSMOS_ENDPOINT=https://your-account-name.documents.azure.com:443/
AZURE_COSMOS_KEY=your-primary-key-here
AZURE_COSMOS_DATABASE_NAME=expert-answers-db
AZURE_COSMOS_CONTAINER_NAME=questions
```

**Important Notes:**
- The endpoint should end with `:443/`
- Use the **PRIMARY KEY**, not the secondary key
- No quotes needed around the values

## Step 3: Install Dependencies

```bash
pip install azure-cosmos==4.5.1
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Step 4: Test the Connection

Run the test script:

```bash
python test_cosmos_connection.py
```

This will:
- ✅ Verify your credentials are set
- ✅ Test the connection to Cosmos DB
- ✅ Create the database and container (if they don't exist)
- ✅ Test adding and retrieving questions

## Step 5: Start Your Server

```bash
uvicorn app.main:app --reload
```

## Step 6: Test the API

### Add a Question
```bash
curl -X POST http://localhost:8000/api/questions/queue \
  -H "Content-Type: application/json" \
  -d '{"question": "What does Vedanta say about evolution?"}'
```

### Upvote a Question
```bash
curl -X POST http://localhost:8000/api/questions/upvote \
  -H "Content-Type: application/json" \
  -d '{"question": "What does Vedanta say about evolution?"}'
```

### Get All Questions
```bash
curl http://localhost:8000/api/questions/queue
```

## Troubleshooting

### Error: "Invalid credentials"
- Double-check your `AZURE_COSMOS_ENDPOINT` and `AZURE_COSMOS_KEY` in `.env`
- Make sure there are no extra spaces or quotes
- Verify you copied the PRIMARY KEY, not the secondary key

### Error: "Database not found"
- This is normal! The database is created automatically on first use
- Run the test script to create it

### Error: "Connection timeout"
- Check your internet connection
- Verify the endpoint URL is correct
- Check if your IP is blocked by firewall rules in Azure Portal

### Error: "ModuleNotFoundError: No module named 'azure.cosmos'"
- Run: `pip install azure-cosmos==4.5.1`

## Next Steps

1. ✅ Test the connection with `test_cosmos_connection.py`
2. ✅ Start your server and test the API endpoints
3. ✅ Integrate with your frontend (see `frontend_example.html`)
4. ✅ The database and container will be created automatically on first use

## Verify in Azure Portal

After running the test, you can verify in Azure Portal:

1. Go to your Cosmos DB account
2. Click on **"Data Explorer"** in the left menu
3. You should see:
   - Database: `expert-answers-db`
   - Container: `questions`
   - Documents with your test questions

