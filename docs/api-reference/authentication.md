---
title: API Authentication
category: API Reference
category_order: 2
order: 1
---

MailSage uses API keys to authenticate requests. You must include your API key in all API requests to our server.

## API Keys {#api-keys}

### Overview {#overview}

API keys are unique identifiers that authenticate your requests to the MailSage API. Each key:

- Is associated with your account
- Has specific permissions
- Can be revoked at any time
- Should be kept secure and private

### Key Types {#key-types}

1. **Live Keys**
   - Format: `ms_live_xxxxxxxxxxxxxxxxxxxx`
   - Used for production environments
   - Full access to all API features
   - Rate limits apply based on your plan

2. **Test Keys**
   - Format: `ms_test_xxxxxxxxxxxxxxxxxxxx`
   - Used for development and testing
   - No actual emails are sent
   - Higher rate limits for testing

## Using Your API Key {#using-your-api-key}

### Request Headers

Include your API key in the `Authorization` header using the Bearer scheme:

```http
Authorization: Bearer YOUR_API_KEY
```

Example request:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/send \
  -H "Authorization: Bearer ms_live_xxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": {
      "email": "user@example.com"
    },
    "subject": "Hello!",
    "body": "Test email"
  }'
```

### Code Examples

**JavaScript**

```javascript
const mailsage = {
  apiKey: process.env.MAILSAGE_API_KEY,
  baseUrl: 'https://api.mailsage.io/api/v1'
};

async function sendEmail(data) {
  const response = await fetch(`${mailsage.baseUrl}/emails/send`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${mailsage.apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  });
  return response.json();
}
```

**Python**

```python
import requests

MAILSAGE_API_KEY = 'your_api_key_here'

def send_email(data):
    response = requests.post(
        'https://api.mailsage.io/api/v1/emails/send',
        headers={
            'Authorization': f'Bearer {MAILSAGE_API_KEY}',
            'Content-Type': 'application/json'
        },
        json=data
    )
    return response.json()
```

## Managing API Keys {#managing-api-keys}

### Creating API Keys {#creating-api-keys}

1. Log in to your [MailSage Dashboard](https://dashboard.mailsage.io)
2. Navigate to Settings → API Keys
3. Click "Create New API Key"
4. Select key type (Live/Test) and permissions
5. Copy and securely store your API key

> ⚠️ **Important**: API keys are only shown once when created. Store them securely!

### Best Practices

1. **Environment Variables**
   - Never hardcode API keys in your code
   - Use environment variables or secure secret management

   ```bash
   # .env file
   MAILSAGE_API_KEY=ms_live_xxxxxxxxxxxxxxxxxxxx
   ```

2. **Key Rotation**
   - Rotate keys periodically
   - Create new key before disabling old one
   - Update all services using the key

3. **Security**
   - Keep keys private
   - Don't share keys in public repositories
   - Use different keys for different environments

4. **Monitoring**
   - Monitor key usage in dashboard
   - Set up alerts for unusual activity
   - Review access logs regularly

## Error Handling {#error-handling}

### Authentication Errors {#authentication-errors}

| Status Code | Description | Solution |
|------------|-------------|-----------|
| 401 | Invalid API key | Check your API key is correct and active |
| 403 | Insufficient permissions | Verify key has required permissions |
| 429 | Rate limit exceeded | Implement backoff strategy |

Example error response:

```json
{
    "error": "Invalid API key provided",
    "status": 401,
    "code": "invalid_api_key"
}
```

### Rate Limiting {#rate-limiting}

Rate limits are based on your plan:

| Plan | Rate Limit |
|------|------------|
| Free | 100 requests/minute |
| Pro | 1000 requests/minute |
| Enterprise | Custom limits |

When rate limited, implement exponential backoff:

```javascript
async function withRetry(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error.status === 429) {
        const waitTime = Math.pow(2, i) * 1000;
        await new Promise(r => setTimeout(r, waitTime));
        continue;
      }
      throw error;
    }
  }
}
```

## Support {#support}

If you encounter authentication issues:

1. Verify your API key is active in dashboard
2. Check you're using the correct key type
3. Ensure key has required permissions
4. Contact support with request ID for help

Need help? Contact [support@mailsage.io](mailto:support@mailsage.io)
