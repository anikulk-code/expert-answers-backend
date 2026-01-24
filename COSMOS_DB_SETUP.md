# Azure Cosmos DB Setup Guide

This guide will help you set up Azure Cosmos DB for the questions and voting feature.

## Prerequisites

- Azure account (free tier available)
- Azure CLI or Azure Portal access

## Step 1: Create Cosmos DB Account

### Option A: Using Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Click "Create a resource"
3. Search for "Azure Cosmos DB"
4. Click "Create"
5. Fill in the details:
   - **Subscription**: Your subscription
   - **Resource Group**: Create new or use existing
   - **Account Name**: `expert-answers-db` (must be globally unique)
   - **API**: Select "Core (SQL)" - Recommended
   - **Location**: Choose closest to your users
   - **Capacity mode**: "Serverless" (recommended for development) or "Provisioned throughput"
6. Click "Review + create", then "Create"
7. Wait for deployment (2-3 minutes)

### Option B: Using Azure CLI

```bash
# Login to Azure
az login

# Create resource group (if needed)
az group create --name expert-answers-rg --location eastus

# Create Cosmos DB account
az cosmosdb create \
  --name expert-answers-db \
  --resource-group expert-answers-rg \
  --default-consistency-level Session \
  --locations regionName=eastus failoverPriority=0 \
  --capabilities EnableServerless
```

## Step 2: Get Connection Details

1. In Azure Portal, go to your Cosmos DB account
2. Navigate to "Keys" in the left menu
3. Copy the following:
   - **URI** (Endpoint)
   - **PRIMARY KEY** (or Secondary Key)

## Step 3: Configure Environment Variables

Add these to your `.env` file:

```env
AZURE_COSMOS_ENDPOINT=https://expert-answers-db.documents.azure.com:443/
AZURE_COSMOS_KEY=your-primary-key-here
AZURE_COSMOS_DATABASE_NAME=expert-answers-db
AZURE_COSMOS_CONTAINER_NAME=questions
```

## Step 4: Install Dependencies

```bash
pip install azure-cosmos==4.5.1
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Step 5: Test the Setup

The database and container will be created automatically on first use. You can test it by:

1. Starting your FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Making a test request:
   ```bash
   curl -X POST http://localhost:8000/api/questions/queue \
     -H "Content-Type: application/json" \
     -d '{"question": "Test question"}'
   ```

3. Check if it was created:
   ```bash
   curl http://localhost:8000/api/questions/queue
   ```

## Database Structure

The Cosmos DB will automatically create:

- **Database**: `expert-answers-db` (configurable via env var)
- **Container**: `questions` (configurable via env var)
- **Partition Key**: `/id`

### Document Schema

Each question document has this structure:

```json
{
  "id": "uuid-string",
  "question": "What does Vedanta say about evolution?",
  "question_normalized": "what does vedanta say about evolution?",
  "upvotes": 5,
  "created_at": "2024-01-06T10:00:00.000Z",
  "updated_at": "2024-01-06T10:30:00.000Z"
}
```

## Cost Considerations

### Serverless Mode (Recommended for Development)
- **Free tier**: First 1000 RU/s and 25 GB storage free per month
- **Pay-per-use**: $0.25 per million RU consumed
- **Storage**: $0.25 per GB/month

### Provisioned Throughput
- Minimum: 400 RU/s (~$24/month)
- Good for: Production with predictable traffic

**Recommendation**: Start with Serverless mode for development and testing.

## Security Best Practices

1. **Never commit keys to git** - Use `.env` file (already in `.gitignore`)
2. **Use Azure Key Vault** for production deployments
3. **Rotate keys regularly** in production
4. **Use IP firewall rules** in production to restrict access
5. **Enable private endpoints** for production

## Troubleshooting

### Error: "CosmosAccessConditionFailedError"
- This is normal - it means the database/container already exists
- The code handles this automatically

### Error: "Invalid credentials"
- Check your `AZURE_COSMOS_ENDPOINT` and `AZURE_COSMOS_KEY` in `.env`
- Make sure there are no extra spaces or quotes

### Error: "Database not found"
- The database is created automatically on first use
- Make sure your Cosmos DB account is active in Azure Portal

### Connection timeout
- Check your network connection
- Verify the endpoint URL is correct
- Check if your IP is blocked by firewall rules

### Error: "Request originated from IP ... through public internet. This is blocked by your Cosmos DB account firewall settings"
- **Cause**: Cosmos DB firewall is blocking your Azure App Service IP
- **Solution**: 
  1. Go to Azure Portal → Cosmos DB account → **Networking**
  2. Enable **"Allow Azure services and resources to access this account"** (recommended)
  3. Or add your App Service's outbound IP addresses to the firewall rules
  4. See `COSMOS_DB_FIREWALL_FIX.md` for detailed steps

## Next Steps

1. Test the API endpoints:
   - `POST /api/questions/queue` - Add question
   - `POST /api/questions/upvote` - Upvote question
   - `GET /api/questions/queue` - Get all questions

2. Integrate with your frontend (see `frontend_example.html`)

3. Monitor usage in Azure Portal:
   - Go to "Metrics" to see request count, data usage, etc.

## Production Deployment

For production, consider:

1. **Provisioned throughput** instead of serverless (for predictable costs)
2. **Azure Key Vault** for storing secrets
3. **Private endpoints** for secure access
4. **Backup and restore** policies
5. **Monitoring and alerts** in Azure Monitor

