---
title: Error Handling Guide
category: Guides
category_order: 3
order: 4
---


Learn how to handle errors and implement robust error handling in your MailSage integration.

## Overview {#overview}

MailSage uses standard HTTP status codes and provides detailed error messages to help you troubleshoot issues:

- Structured error responses
- Retry recommendations
- Rate limit information
- Detailed error codes

## Error Response Format {#error-response-format}

All API errors follow a consistent format:

```json
{
    "error": "Descriptive error message",
    "code": "error_code",
    "details": {
        "field": "Additional information"
    },
    "request_id": "req_xyz123"
}
```

## Common Error Codes {#common-error-codes}

### Authentication Errors (401, 403)

| Code | Description | Solution |
|------|-------------|----------|
| `invalid_api_key` | Invalid API key | Check your API key |
| `expired_api_key` | API key has expired | Generate a new key |
| `insufficient_permissions` | Missing required permissions | Check key permissions |

### Request Errors (400)

| Code | Description | Solution |
|------|-------------|----------|
| `invalid_request` | Malformed request | Check request format |
| `missing_required` | Missing required fields | Add required fields |
| `invalid_parameter` | Invalid parameter value | Check parameter values |

### Resource Errors (404)

| Code | Description | Solution |
|------|-------------|----------|
| `template_not_found` | Template doesn't exist | Verify template ID |
| `smtp_not_found` | SMTP config not found | Check SMTP config ID |

### Rate Limiting (429)

| Code | Description | Solution |
|------|-------------|----------|
| `rate_limit_exceeded` | Too many requests | Implement backoff |
| `daily_limit_exceeded` | Daily sending limit reached | Wait or upgrade plan |

## Handling Rate Limits {#handling-rate-limits}

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### Implementing Backoff

```python
import time
from typing import Callable
from functools import wraps

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except RateLimitError as e:
                    retries += 1
                    if retries == max_retries:
                        raise

                    # Exponential backoff
                    delay = base_delay * (2 ** (retries - 1))
                    time.sleep(delay)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@with_retry(max_retries=3)
def send_email(recipient: str, subject: str, body: str):
    # Your email sending code here
    pass
```

## SMTP Errors {#smtp-errors}

### Common SMTP Issues

1. **Authentication Failures**

   ```json
   {
       "error": "SMTP authentication failed",
       "code": "smtp_auth_error",
       "details": {
           "smtp_code": 535,
           "smtp_response": "Authentication credentials invalid"
       }
   }
   ```

2. **Connection Issues**

   ```json
   {
       "error": "SMTP connection failed",
       "code": "smtp_connection_error",
       "details": {
           "host": "smtp.example.com",
           "port": 587
       }
   }
   ```

### Handling SMTP Failures {#handling-smtp-failures}

```python
from mailsage import MailSageClient
from mailsage.exceptions import SMTPError

client = MailSageClient('your_api_key')

try:
    response = client.send_email(
        recipient='user@example.com',
        subject='Test',
        body='Hello'
    )
except SMTPError as e:
    if e.code == 'smtp_auth_error':
        # Refresh SMTP credentials
        pass
    elif e.code == 'smtp_connection_error':
        # Try backup SMTP server
        pass
    else:
        # Handle other SMTP errors
        pass
```

## Template Errors {#template-errors}

### Validation Errors

```json
{
    "error": "Template validation failed",
    "code": "template_error",
    "details": {
        "line": 5,
        "message": "Missing closing tag for <div>"
    }
}
```

### Variable Errors

```json
{
    "error": "Template rendering failed",
    "code": "template_variable_error",
    "details": {
        "missing_variables": ["name", "company"]
    }
}
```

## Best Practices {#best-practices}

1. **Always Check Response Status**

   ```python
   response = client.send_email(...)
   if response.get('status') == 'queued':
       job_id = response['job_id']
       # Track job status
   ```

2. **Implement Proper Logging**

   ```python
   import logging

   logging.error(f"Email sending failed: {e.code}", extra={
       'request_id': e.request_id,
       'recipient': recipient,
       'template_id': template_id
   })
   ```

3. **Use Request IDs**
   - Include request ID in support inquiries
   - Log request IDs for debugging
   - Track related events using request ID

4. **Handle Timeouts**

   ```python
   try:
       response = client.send_email(..., timeout=10)
   except TimeoutError:
       # Handle timeout
       pass
   ```

## Support {#support}

If you need help debugging errors:

1. Check our [status page](https://status.mailsage.io)
2. Contact support with:
   - Request ID
   - Error code and message
   - Timestamp of the error
   - Any relevant logs

Need help? Contact [support@mailsage.io](mailto:support@mailsage.io)
