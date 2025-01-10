---
title: Sending Emails Guide
category: Guides
category_order: 3
order: 2
---

Learn how to send emails using the MailSage API, from basic single emails to advanced batch operations.

## Overview {#overview}

MailSage provides flexible email sending capabilities:

- Single and batch email sending
- Template support with variable substitution
- SMTP provider selection
- Delivery tracking
- Queue management

## Sending Single Emails {#sending-single-emails}

### Basic Email

Send a simple email without a template:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/send \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "recipient": {
      "email": "user@example.com"
    },
    "subject": "Hello from MailSage",
    "body": "This is a test email."
  }'
```

### Using Templates

Send an email using a template with variables:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/send \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template_123",
    "recipient": {
      "email": "user@example.com",
      "variables": {
        "name": "John",
        "company": "Acme Inc"
      }
    },
    "subject": "Welcome to {{ company }}!"
  }'
```

## Sending Batch Emails {#sending-batch-emails}

### Basic Batch

Send the same email to multiple recipients:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/batch \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template_123",
    "recipients": [
      {
        "email": "user1@example.com",
        "variables": {
          "name": "John",
          "company": "Acme Inc"
        }
      },
      {
        "email": "user2@example.com",
        "variables": {
          "name": "Jane",
          "company": "Beta Corp"
        }
      }
    ],
    "subject": "Welcome to {{ company }}!"
  }'
```

### Campaign Management

Track batch emails as a campaign:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/batch \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "template_123",
    "recipients": [...],
    "subject": "Welcome!",
    "campaign_id": "campaign_xyz"
  }'
```

## Job Control {#job-control}

### Checking Status

Monitor the status of your email jobs:

```bash
curl -X GET https://api.mailsage.io/api/v1/emails/jobs/{job_id} \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Controlling Jobs

Pause, resume, or stop email jobs:

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/jobs/{job_id}/control \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "pause"  # or "resume" or "stop"
  }'
```

## Best Practices {#best-practices}

1. **Template Usage**
   - Use templates for consistent emails
   - Test templates before sending
   - Keep variables organized

2. **Batch Processing**
   - Use batch endpoints for multiple recipients
   - Include campaign IDs for tracking
   - Monitor job status

3. **Error Handling**
   - Check response codes
   - Monitor delivery status
   - Set up webhooks for updates

## Code Examples {#code-examples}

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

    def send_email(self, recipient, subject, body=None, template_id=None, variables=None):
        data = {
            'recipient': {
                'email': recipient,
                'variables': variables or {}
            },
            'subject': subject
        }

        if template_id:
            data['template_id'] = template_id
        else:
            data['body'] = body

        response = requests.post(
            f'{self.base_url}/emails/send',
            headers=self.headers,
            json=data
        )
        return response.json()

    def send_batch(self, recipients, subject, template_id, campaign_id=None):
        data = {
            'recipients': recipients,
            'subject': subject,
            'template_id': template_id
        }

        if campaign_id:
            data['campaign_id'] = campaign_id

        response = requests.post(
            f'{self.base_url}/emails/batch',
            headers=self.headers,
            json=data
        )
        return response.json()
```

### Node.js

```javascript
class MailSageClient {
    constructor(apiKey) {
        this.apiKey = apiKey;
        this.baseUrl = 'https://api.mailsage.io/api/v1';
        this.headers = {
            'Authorization': `Bearer ${apiKey}`,
            'Content-Type': 'application/json'
        };
    }

    async sendEmail(recipient, subject, { body, templateId, variables } = {}) {
        const data = {
            recipient: {
                email: recipient,
                variables: variables || {}
            },
            subject
        };

        if (templateId) {
            data.template_id = templateId;
        } else {
            data.body = body;
        }

        const response = await fetch(`${this.baseUrl}/emails/send`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(data)
        });
        return response.json();
    }

    async sendBatch(recipients, subject, templateId, campaignId = null) {
        const data = {
            recipients,
            subject,
            template_id: templateId
        };

        if (campaignId) {
            data.campaign_id = campaignId;
        }

        const response = await fetch(`${this.baseUrl}/emails/batch`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(data)
        });
        return response.json();
    }
}
```

## Troubleshooting {#troubleshooting}

### Common Issues {#common-issues}

1. **Template Errors**
   - Check template variables match
   - Verify template exists
   - Test template rendering

2. **Rate Limits**
   - Monitor SMTP limits
   - Use batch sending
   - Check account quotas

3. **Delivery Issues**
   - Verify recipient emails
   - Check SMTP configuration
   - Monitor bounce rates

### Error Codes {#error-codes}

| Code | Description | Solution |
|------|-------------|----------|
| `invalid_recipient` | Invalid email address | Check email format |
| `template_error` | Template rendering failed | Verify variables |
| `smtp_error` | SMTP sending failed | Check configuration |
| `rate_limit` | Rate limit exceeded | Adjust sending rate |

## Next Steps

1. [Set up webhooks](../webhooks)
2. [Monitor analytics](../analytics)
3. [Handle bounces](../bounce-handling)

Need help? Contact [support@mailsage.io](mailto:support@mailsage.io)
