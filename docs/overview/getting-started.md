---
title: Getting Started with MailSage
category: Overview
category_order: 1
order: 2
---

Get up and running with MailSage in minutes. This guide will help you start sending emails through our API.

## Quick Start

### 1. Sign Up {#sign-up}

Create your MailSage account to get your API keys.

### 2. Add SMTP Configuration {#add-smtp}

Configure your SMTP provider through our API:

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
    "use_tls": true
  }'
```

### 3. Send Your First Email {#send-first-email}

```bash
curl -X POST https://api.mailsage.io/api/v1/emails/send \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to": "recipient@example.com",
    "subject": "Hello from MailSage",
    "body": "Your first email through MailSage!"
  }'
```

## Integration Examples {#integration-examples}

### Python {#python}

```python
import requests

MAILSAGE_API_KEY = 'your_api_key'
BASE_URL = 'https://api.mailsage.io/api/v1'

def send_email(to, subject, body):
    response = requests.post(
        f'{BASE_URL}/emails/send',
        headers={
            'Authorization': f'Bearer {MAILSAGE_API_KEY}',
            'Content-Type': 'application/json'
        },
        json={
            'to': to,
            'subject': subject,
            'body': body
        }
    )
    return response.json()
```

### JavaScript/Node.js {#javascript-nodejs}

```javascript
const axios = require('axios');

const mailsage = {
  apiKey: 'your_api_key',
  baseUrl: 'https://api.mailsage.io/api/v1'
};

async function sendEmail(to, subject, body) {
  try {
    const response = await axios.post(
      `${mailsage.baseUrl}/emails/send`,
      {
        to,
        subject,
        body
      },
      {
        headers: {
          'Authorization': `Bearer ${mailsage.apiKey}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  } catch (error) {
    console.error('Error sending email:', error.response.data);
    throw error;
  }
}
```

## Next Steps {#next-steps}

1. Explore the [API Reference](/api-reference/authentication) for detailed endpoints
2. Learn about [Template Management](/guides/template-variables)
3. Set up [Webhook Integration](/webhooks/overview)
4. Review [Error Handling](/guides/error-handling)

---
