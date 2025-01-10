---
title: SMTP Configuration Guide
category: Guides
category_order: 3
order: 1
---


This guide explains how to set up and manage SMTP configurations in MailSage.

## Overview

MailSage allows you to use your own SMTP providers while providing powerful management features:

- Multiple SMTP provider support
- Automatic failover
- Rate limiting and queueing
- Delivery tracking
- Secure credential storage

## Setting Up SMTP

### 1. Gather SMTP Credentials

You'll need the following information from your SMTP provider:

- SMTP server hostname
- Port number (usually 587 for TLS)
- Username
- Password
- From email address

### 2. Add SMTP Configuration

Use the API to add your SMTP configuration:

```bash
curl -X POST https://api.mailsage.io/api/v1/smtp/configs \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Primary SMTP",
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "your-email@gmail.com",
    "password": "your-password",
    "use_tls": true,
    "from_email": "noreply@yourdomain.com",
    "is_default": true,
    "daily_limit": 1000
  }'
```

### 3. Test Configuration

Always test your SMTP configuration before using it:

```bash
curl -X POST https://api.mailsage.io/api/v1/smtp/configs/{config_id}/test \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": "test@yourdomain.com"
  }'
```

## Managing Multiple SMTP Configurations

### Default Configuration

- Set `is_default: true` when creating/updating an SMTP config
- Used when no specific SMTP configuration is specified in email requests
- Only one default configuration allowed per account

### Daily Limits

- Set `daily_limit` to control maximum emails per day
- Defaults to 100 if not specified
- Resets automatically at midnight UTC
- Monitor usage through the API

## Best Practices

1. **Security**
   - Use environment variables for credentials
   - Enable TLS whenever possible
   - Regularly rotate SMTP passwords

2. **Reliability**
   - Set up multiple SMTP configurations for failover
   - Test configurations regularly
   - Monitor delivery rates and errors

3. **Rate Limiting**
   - Set appropriate daily limits
   - Consider provider-specific rate limits
   - Use batch sending for large volumes

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify credentials are correct
   - Check if 2FA is enabled (use app password if needed)
   - Ensure account has SMTP access enabled

2. **Connection Failed**
   - Verify hostname and port
   - Check firewall settings
   - Ensure TLS is properly configured

3. **Rate Limit Exceeded**
   - Check daily limit settings
   - Monitor provider rate limits
   - Consider upgrading plan or adding providers

### Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `smtp_auth_error` | Authentication failed | Check credentials |
| `smtp_connection_error` | Cannot connect to server | Verify host/port |
| `smtp_rate_limit` | Rate limit exceeded | Check limits |
| `smtp_validation_failed` | Invalid configuration | Review settings |

## Code Examples

### Python

```python
import requests

class MailSageClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = 'https://api.mailsage.io/api/v1'
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def add_smtp_config(self, config_data):
        response = requests.post(
            f'{self.base_url}/smtp/configs',
            headers=self.headers,
            json=config_data
        )
        return response.json()

    def test_smtp_config(self, config_id, test_email):
        response = requests.post(
            f'{self.base_url}/smtp/configs/{config_id}/test',
            headers=self.headers,
            json={'recipient': test_email}
        )
        return response.json()
```

### Node.js

```javascript
class MailSageClient {
    constructor(jwToken) {
        this.jwToken = jwToken;
        this.baseUrl = 'https://api.mailsage.io/api/v1';
        this.headers = {
            'Authorization': `Bearer ${jwToken}`,
            'Content-Type': 'application/json'
        };
    }

    async addSmtpConfig(configData) {
        const response = await fetch(`${this.baseUrl}/smtp/configs`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(configData)
        });
        return response.json();
    }

    async testSmtpConfig(configId, testEmail) {
        const response = await fetch(
            `${this.baseUrl}/smtp/configs/${configId}/test`,
            {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ recipient: testEmail })
            }
        );
        return response.json();
    }
}
```

## Next Steps

1. [Set up email templates](../templates)
2. [Configure webhooks](../webhooks)
3. [Monitor email analytics](../analytics)

Need help? Contact [support@mailsage.io](mailto:support@mailsage.io)
