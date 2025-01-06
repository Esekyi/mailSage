---
title: API Key Management
category: API Reference
order: 2
---

# API Key Management

MailSage uses API keys to authenticate requests to the API. Each API key is associated with a user account and can have specific permissions and restrictions.

## Overview

- API keys are the primary method for authenticating with the MailSage API
- Two types of keys: `live` and `test`
- Keys can have specific permissions
- Optional expiration dates for enhanced security
- Rate limiting and usage tracking included

## Security Best Practices

1. **Key Storage**
   - Never expose API keys in client-side code
   - Use environment variables or secure key management systems
   - Don't commit API keys to version control

2. **Key Rotation**
   - Rotate keys regularly (recommended every 90 days)
   - Create new keys before revoking old ones
   - Use expiration dates for automatic rotation

3. **Permission Management**
   - Follow the principle of least privilege
   - Use different keys for different services/environments
   - Regularly audit key permissions and usage

## API Reference

### Create API Key

Create a new API key for accessing the MailSage API.

#### Endpoint

```http
POST /api/v1/api-keys
```

#### Headers

```http
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json
```

#### Request Body

```json
{
    "name": "Production API Key",
    "key_type": "live",                                  // Optional, default: "live"
    "permissions": ["send_email", "manage_templates"],   // Optional
    "expires_in_days": 365                              // Optional
}
```

#### Response

```json
{
    "message": "API key created successfully",
    "api_key": {
        "id": 1,
        "name": "Production API Key",
        "key_prefix": "abc123",
        "key_type": "live",
        "permissions": ["send_email", "manage_templates"],
        "expires_at": "2024-12-31T23:59:59Z",
        "is_active": true,
        "created_at": "2023-12-31T00:00:00Z"
    },
    "key": "ms_abc123_xyz..."  // Full key, only shown once
}
```

#### Available Permissions

| Permission | Description |
|------------|-------------|
| `send_email` | Send emails through the API |
| `manage_templates` | Create and manage email templates |
| `manage_smtp` | Configure SMTP settings |
| `view_analytics` | Access email analytics |
| `webhook_management` | Manage webhook configurations |

### List API Keys

Retrieve all active API keys for your account.

#### Endpoint

```http
GET /api/v1/api-keys
```

#### Response

```json
{
    "api_keys": [
        {
            "id": 1,
            "name": "Production API Key",
            "key_prefix": "abc123",
            "key_type": "live",
            "permissions": ["send_email", "manage_templates"],
            "last_used_at": "2023-12-31T12:00:00Z",
            "expires_at": "2024-12-31T23:59:59Z",
            "is_active": true,
            "created_at": "2023-12-31T00:00:00Z",
            "daily_requests": 150
        }
    ]
}
```

### Revoke API Key

Revoke an existing API key. This action cannot be undone.

#### Endpoint

```http
DELETE /api/v1/api-keys/{key_id}
```

#### Response

```json
{
    "message": "API key revoked successfully"
}
```

### Get API Key Usage

Get detailed usage statistics for an API key.

#### Endpoint

```http
GET /api/v1/api-keys/{key_id}/usage?days=30
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| days | integer | 30 | Number of days of history to return |

#### Response

```json
{
    "usage_stats": {
        "total_requests": 1500,
        "success_requests": 1450,
        "error_requests": 50,
        "success_rate": 96.67,
        "endpoint_usage": {
            "/api/v1/emails/send": 1000,
            "/api/v1/emails/batch": 500
        },
        "daily_average": 50
    }
}
```

## Rate Limiting and Quotas

- Rate limits are applied per API key
- Default rate: 100 requests per minute
- Burst allowance: 150 requests
- Headers returned with each response:
  - `X-RateLimit-Limit`: Total requests allowed per minute
  - `X-RateLimit-Remaining`: Remaining requests in the current window
  - `X-RateLimit-Reset`: Time when the rate limit resets

## Code Examples

### Python

```python
import requests

class MailSageClient:
    def __init__(self, api_key, base_url="https://api.mailsage.io"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def create_api_key(self, name, key_type="live", permissions=None):
        response = requests.post(
            f"{self.base_url}/api/v1/api-keys",
            headers=self.headers,
            json={
                "name": name,
                "key_type": key_type,
                "permissions": permissions
            }
        )
        return response.json()

    def list_api_keys(self):
        response = requests.get(
            f"{self.base_url}/api/v1/api-keys",
            headers=self.headers
        )
        return response.json()

    def revoke_api_key(self, key_id):
        response = requests.delete(
            f"{self.base_url}/api/v1/api-keys/{key_id}",
            headers=self.headers
        )
        return response.json()
```

### JavaScript

```javascript
class MailSageClient {
    constructor(apiKey, baseUrl = 'https://api.mailsage.io') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async createApiKey(name, keyType = 'live', permissions = null) {
        const response = await fetch(`${this.baseUrl}/api/v1/api-keys`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                name,
                key_type: keyType,
                permissions
            })
        });
        return response.json();
    }

    async listApiKeys() {
        const response = await fetch(`${this.baseUrl}/api/v1/api-keys`, {
            headers: this.headers
        });
        return response.json();
    }

    async revokeApiKey(keyId) {
        const response = await fetch(`${this.baseUrl}/api/v1/api-keys/${keyId}`, {
            method: 'DELETE',
            headers: this.headers
        });
        return response.json();
    }
}
```

## Troubleshooting

### Common Issues

1. **Invalid API Key**
   - Check if the key is active and not expired
   - Verify the key has the required permissions
   - Ensure you're using the correct key type (test/live)

2. **Rate Limit Exceeded**
   - Check your current usage in the dashboard
   - Consider implementing exponential backoff
   - Contact support for rate limit increases

3. **Permission Denied**
   - Verify the key has the necessary permissions
   - Check if the key has expired
   - Ensure the key hasn't been revoked

### Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 401 | Invalid API key | Check your API key is valid and active |
| 403 | Insufficient permissions | Verify key permissions |
| 429 | Rate limit exceeded | Implement backoff strategy |
| 404 | API key not found | Check the key ID is correct |

## Support

If you encounter any issues or need assistance:

- Check our [troubleshooting guide](#troubleshooting)
- Contact support at <support@mailsage.io>
- Join our [Discord community](https://discord.gg/mailsage)
