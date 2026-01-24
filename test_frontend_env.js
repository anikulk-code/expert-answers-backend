/**
 * Test script to verify frontend environment variables
 * Run this in browser console on deployed site to debug
 */

console.log('=== Frontend Environment Variables Debug ===');
console.log('REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
console.log('REACT_APP_ENABLE_DEBUG:', process.env.REACT_APP_ENABLE_DEBUG);
console.log('showDebug would be:', process.env.REACT_APP_ENABLE_DEBUG === 'true');

// Test API connection
const apiUrl = process.env.REACT_APP_API_URL || 'https://expertanswersapi-ege8htfcg5a0bgbk.westus2-01.azurewebsites.net';
console.log('Using API URL:', apiUrl);

// Test health endpoint
fetch(`${apiUrl}/health`)
  .then(res => res.json())
  .then(data => console.log('✅ Backend health check:', data))
  .catch(err => console.error('❌ Backend health check failed:', err));

// Test search endpoint
fetch(`${apiUrl}/api/answers/v1?question=test&count=1`)
  .then(res => res.json())
  .then(data => {
    console.log('✅ Search endpoint works');
    console.log('Queue info in response:', data.queueInfo);
    console.log('Similar questions:', data.queueInfo?.similarQuestions);
  })
  .catch(err => console.error('❌ Search endpoint failed:', err));
