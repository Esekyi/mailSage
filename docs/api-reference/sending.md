---
title: Sending Emails
category: API Reference
category_order: 2
order: 4
---

The MailSage API provides endpoints for sending both single and batch emails. All endpoints require API key authentication.

## Single Email Sending {#single-email-sending}

Send a single email with optional template and variable support.

### Endpoint (POST) - Send Single Email

```http
POST /api/v1/emails/send
```

### Headers

```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### Request Body (JSON)

```json
{
    "template_id": "id",          // Optional: Template ID
    "recipient": {
        "email": "user@example.com",
        "variables": {              // Optional: Required if using template
            "name": "John",
            "company": "Acme Inc"
        }
    },
    "subject": "Welcome to MailSage!",
    "body": "Email content...",     // Optional: Required if no template_id
    "smtp_id": "id"               // Optional: Uses default if not specified
}
```

### Response (JSON)

```json
{
    "message": "Email queued successfully",
    "job_id": "123",
    "task_id": "abc-xyz",
    "tracking_id": "track-123",
    "status": "queued"
}
```

### Example

```javascript
// Using fetch
const response = await fetch('https://api.mailsage.io/api/v1/emails/send', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    recipient: {
      email: 'user@example.com',
      variables: { name: 'John' }
    },
    template_id: 'template-123',
    subject: 'Welcome!'
  })
});

const data = await response.json();
```

```python
# Using requests
import requests

response = requests.post(
    'https://api.mailsage.io/api/v1/emails/send',
    headers={
        'Authorization': 'Bearer YOUR_API_KEY',
        'Content-Type': 'application/json'
    },
    json={
        'recipient': {
            'email': 'user@example.com',
            'variables': {'name': 'John'}
        },
        'template_id': 'template-123',
        'subject': 'Welcome!'
    }
)

data = response.json()
```

## Batch Email Sending

Send emails to multiple recipients in a single request.

### Endpoint (POST) - Send Batch Emails

```http
POST /api/v1/emails/batch
```

### Request Body

```json
{
    "template_id": "uuid",
    "recipients": [
        {
            "email": "user1@example.com",
            "variables": {
                "name": "John",
                "plan": "Pro"
            }
        },
        {
            "email": "user2@example.com",
            "variables": {
                "name": "Jane",
                "plan": "Enterprise"
            }
        }
    ],
    "subject": "Welcome to MailSage!",
    "smtp_id": "uuid",           // Optional
    "campaign_id": "uuid"        // Optional, for tracking
}
```

### Response body (JSON)

```json
{
    "message": "Batch email queued successfully",
    "job_id": "123",
    "task_id": "abc-xyz",
    "tracking_id": "track-123",
    "status": "queued",
    "recipient_count": 2
}
```

## Job Control {#job-control}

Control and monitor email sending jobs.

### Check Job Status

```http
GET /api/v1/emails/jobs/{job_id}/status
```

### Response

```json
{
    "id": "123",
    "status": "processing",
    "progress": {
        "total": 100,
        "sent": 45,
        "failed": 2,
        "pending": 53,
        "percentage": 45.0
    },
    "started_at": "2023-12-24T10:00:00Z",
    "updated_at": "2023-12-24T10:01:00Z"
}
```

### Control Job

```http
POST /api/v1/emails/jobs/{job_id}/control
```

Request body:

```json
{
    "action": "pause" // or "resume" or "stop"
}
```

## Error Handling {#error-handling}

The API uses standard HTTP response codes:

- `202`: Request accepted and queued
- `400`: Invalid request
- `401`: Invalid API key
- `404`: Resource not found
- `429`: Rate limit exceeded
- `500`: Server error

Error responses include a message:

```json
{
    "error": "Detailed error message"
}
```
