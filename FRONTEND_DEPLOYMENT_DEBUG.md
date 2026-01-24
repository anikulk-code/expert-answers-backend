# Frontend Deployment Debugging Guide

## Required Environment Variables

The frontend requires the following environment variables to be set in your deployment platform:

### 1. `REACT_APP_API_URL` (Required)
- **Purpose**: Backend API URL
- **Example**: `https://expertanswersapi-ege8htfcg5a0bgbk.westus2-01.azurewebsites.net`
- **Default**: Falls back to Azure URL if not set
- **Where to set**: Azure Static Web Apps → Configuration → Application Settings

### 2. `REACT_APP_ENABLE_DEBUG` (Optional)
- **Purpose**: Show/hide the debug tab (only for local development)
- **Values**: `'true'` to show, `'false'` or unset to hide
- **Default**: Hidden (debug tab not shown)
- **Where to set**: Azure Static Web Apps → Configuration → Application Settings

## How to Debug Frontend Deployment Issues

### Step 1: Check Build Logs
1. Go to Azure Portal → Your Static Web App
2. Navigate to **Deployment history**
3. Check the latest deployment logs for:
   - Build errors
   - Missing dependencies
   - Environment variable issues

### Step 2: Verify Environment Variables
1. Go to Azure Portal → Your Static Web App
2. Navigate to **Configuration** → **Application Settings**
3. Verify these variables are set:
   ```
   REACT_APP_API_URL=https://your-backend-url.azurewebsites.net
   REACT_APP_ENABLE_DEBUG=false
   ```
4. **Important**: After adding/updating environment variables, you need to **redeploy** the app

### Step 3: Check Browser Console
1. Open your deployed frontend in a browser
2. Open Developer Tools (F12)
3. Check the **Console** tab for:
   - API connection errors
   - CORS errors
   - Missing environment variable warnings
   - Network errors

### Step 4: Test API Connection
1. In browser console, run:
   ```javascript
   console.log('API URL:', process.env.REACT_APP_API_URL);
   ```
2. Check if the API URL is correct
3. Test API endpoint directly:
   ```bash
   curl https://your-backend-url.azurewebsites.net/health
   ```

### Step 5: Check Network Tab
1. Open Developer Tools → **Network** tab
2. Reload the page
3. Look for:
   - Failed API requests (red status codes)
   - CORS errors
   - 404 errors for API endpoints
   - Timeout errors

## Common Issues and Solutions

### Issue 1: "API URL is undefined"
**Symptom**: Frontend can't connect to backend
**Solution**: 
- Set `REACT_APP_API_URL` in Azure Static Web Apps configuration
- Redeploy after setting environment variables

### Issue 2: CORS Errors
**Symptom**: Browser console shows CORS policy errors
**Solution**:
- Set `ALLOWED_ORIGINS` in backend environment variables
- Include your frontend URL: `https://your-frontend.azurestaticapps.net`
- Restart backend after setting

### Issue 3: Build Fails
**Symptom**: Deployment shows build errors
**Solution**:
- Check `package.json` for all dependencies
- Verify Node.js version compatibility
- Check build logs for specific error messages
- **Common**: ESLint warnings are treated as errors in CI (`process.env.CI = true`)
  - Fix: Remove unused variables, fix React Hook dependencies, or add eslint-disable comments with explanations
  - Test locally: `npm run build` should succeed without warnings

### Issue 4: Environment Variables Not Working
**Symptom**: Variables set but not accessible in app
**Solution**:
- **Important**: React environment variables must start with `REACT_APP_`
- Variables are embedded at build time, not runtime
- You must **rebuild and redeploy** after changing environment variables
- Clear browser cache after redeployment

### Issue 5: Debug Tab Showing in Production
**Symptom**: Debug tab visible on deployed site
**Solution**:
- Set `REACT_APP_ENABLE_DEBUG=false` in Azure configuration
- Or leave it unset (defaults to hidden)
- Redeploy after setting

## Azure Static Web Apps Configuration

### Setting Environment Variables in Azure Portal:
1. Go to Azure Portal → Your Static Web App
2. Click **Configuration** in the left menu
3. Click **Application Settings** tab
4. Click **+ Add** to add new environment variables
5. Add:
   - **Name**: `REACT_APP_API_URL`
   - **Value**: `https://your-backend-url.azurewebsites.net`
6. Click **Save**
7. **Important**: Redeploy the app after saving

### Build Configuration:
- **App location**: `/` (root of frontend repo)
- **Api location**: (leave empty, backend is separate)
- **Output location**: `build` (default React build output)

## Testing Checklist

After deployment, verify:
- [ ] Frontend loads without errors
- [ ] Browser console shows no errors
- [ ] API URL is correctly set (check console.log)
- [ ] Search functionality works
- [ ] Tags/Explore page loads
- [ ] Debug tab is hidden (if `REACT_APP_ENABLE_DEBUG` is not 'true')
- [ ] API requests succeed (check Network tab)
- [ ] No CORS errors in console

## Quick Debug Commands

### Check if environment variables are set:
```bash
# In browser console
console.log('API URL:', process.env.REACT_APP_API_URL);
console.log('Debug enabled:', process.env.REACT_APP_ENABLE_DEBUG);
```

### Test backend API:
```bash
curl https://your-backend-url.azurewebsites.net/health
curl "https://your-backend-url.azurewebsites.net/api/answers/v1?question=test"
```

### Check frontend build:
```bash
cd expert-answers-vedanta-frontend
npm run build
# Check if build succeeds locally
```

## Need More Help?

1. Check Azure Static Web Apps logs
2. Check backend API logs
3. Verify all environment variables are set correctly
4. Test API endpoints directly
5. Check browser console for specific error messages
