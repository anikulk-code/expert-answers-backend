# Fix Cosmos DB Firewall Error

## Problem
Error: `Request originated from IP 52.175.235.45 through public internet. This is blocked by your Cosmos DB account firewall settings.`

This happens when your Azure App Service tries to connect to Cosmos DB, but the Cosmos DB firewall is blocking it.

## Quick Fix (Recommended for Azure-hosted services)

### Option 1: Allow All Azure Services (Easiest)

1. Go to **Azure Portal** → Your **Cosmos DB account**
2. Navigate to **Networking** in the left menu
3. Under **Firewall and virtual networks**:
   - Check the box: **"Allow Azure services and resources to access this account"**
   - Click **Save**
4. Wait 1-2 minutes for the change to propagate

**This is the recommended approach** when your backend is hosted on Azure App Service, as it automatically allows all Azure services to connect.

### Option 2: Add Specific IP Address

If you prefer to be more restrictive:

1. Go to **Azure Portal** → Your **Cosmos DB account**
2. Navigate to **Networking** → **Firewall and virtual networks**
3. Under **Firewall rules**, click **+ Add my current IP** (if you're accessing from your computer)
4. Or manually add the IP: `52.175.235.45`
5. Click **Save**

**Note**: Azure App Service IPs can change, so Option 1 is more reliable.

### Option 3: Get All Outbound IPs from App Service

If you want to be specific but handle IP changes:

1. Go to **Azure Portal** → Your **App Service** (expertanswersapi)
2. Navigate to **Properties** in the left menu
3. Find **Outbound IP addresses** - copy all IPs listed
4. Go to **Cosmos DB account** → **Networking** → **Firewall**
5. Add each IP address from the App Service
6. Click **Save**

## Verify the Fix

After saving the firewall changes:

1. Wait 1-2 minutes for changes to propagate
2. Test the API from your frontend
3. The error should be gone and queries should work

## Alternative: Use Private Endpoint (Production)

For production, consider using **Private Endpoints** instead of public firewall rules:

1. Go to **Cosmos DB account** → **Networking**
2. Under **Private endpoint connections**, click **+ Private endpoint**
3. Configure it to connect to your App Service's VNet
4. This provides better security and doesn't require firewall rules

## Current Error Details

- **Blocked IP**: `52.175.235.45`
- **Source**: Azure App Service outbound IP
- **Solution**: Enable "Allow Azure services" or add the IP to firewall rules
