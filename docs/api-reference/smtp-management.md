---
title: SMTP Management
category: API Reference
order: 2
---

# SMTP Management

Manage your SMTP configurations through the MailSage API.

## Add SMTP Configuration

Create a new SMTP configuration for sending emails.

### Endpoint

<ApiEndpoint method="POST" url="/api/v1/smtp/configs" />

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Friendly name for this configuration |
| host | string | Yes | SMTP server hostname |
| port | integer | Yes | SMTP server port |
| username | string | Yes | SMTP authentication username |
| password | string | Yes | SMTP authentication password |
| use_tls | boolean | No | Use TLS encryption (default: true) |
| from_email | string | Yes | Default sender email address |
| is_default | boolean | No | Set as default configuration |

```json
{
  "name": "Primary SMTP",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "password": "your-password",
  "use_tls": true,
  "from_email": "noreply@yourdomain.com",
  "is_default": true
}
```

### Response

```json
{
  "id": 1,
  "name": "Primary SMTP",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "from_email": "noreply@yourdomain.com",
  "is_default": true,
  "created_at": "2024-01-06T12:00:00Z"
}
```

### Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 400 | invalid_request | Missing or invalid parameters |
| 401 | unauthorized | Invalid API key |
| 403 | forbidden | Insufficient permissions |
| 429 | rate_limit | Rate limit exceeded |

## List SMTP Configurations

Retrieve all SMTP configurations for your account.

### Endpoint

<ApiEndpoint method="GET" url="/api/v1/smtp/configs" />

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | No | Page number (default: 1) |
| per_page | integer | No | Items per page (default: 20) |

### Response

```json
{
  "data": [
    {
      "id": 1,
      "name": "Primary SMTP",
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "your-email@gmail.com",
      "from_email": "noreply@yourdomain.com",
      "is_default": true,
      "created_at": "2024-01-06T12:00:00Z"
    }
  ],
  "meta": {
    "current_page": 1,
    "total_pages": 1,
    "total_items": 1
  }
}
```

## Update SMTP Configuration

Update an existing SMTP configuration.

### Endpoint

<ApiEndpoint method="PUT" url="/api/v1/smtp/configs/:id" />

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| id | integer | SMTP configuration ID |

### Request Body

Same fields as Add SMTP Configuration, all optional.

```json
{
  "name": "Updated SMTP",
  "from_email": "new-sender@yourdomain.com"
}
```

### Response

```json
{
  "id": 1,
  "name": "Updated SMTP",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "your-email@gmail.com",
  "from_email": "new-sender@yourdomain.com",
  "is_default": true,
  "updated_at": "2024-01-06T13:00:00Z"
}
```

## Delete SMTP Configuration

Delete an SMTP configuration.

### Endpoint

<ApiEndpoint method="DELETE" url="/api/v1/smtp/configs/:id" />

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| id | integer | SMTP configuration ID |

### Response

```json
{
  "message": "SMTP configuration deleted successfully"
}
```

## Test SMTP Configuration

Test an SMTP configuration by sending a test email.

### Endpoint

<ApiEndpoint method="POST" url="/api/v1/smtp/configs/:id/test" />

### URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| id | integer | SMTP configuration ID |

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| recipient | string | Yes | Test email recipient |

```json
{
  "recipient": "test@example.com"
}
```

### Response

```json
{
  "message": "Test email sent successfully",
  "delivery_id": "del_123xyz"
}
```

## Common Errors

### Authentication Failed

```json
{
  "error": "SMTP authentication failed",
  "code": "smtp_auth_error",
  "message": "Invalid username or password"
}
```

### Connection Failed

```json
{
  "error": "SMTP connection failed",
  "code": "smtp_connection_error",
  "message": "Could not connect to SMTP server"
}
```

### Rate Limited

```json
{
  "error": "Rate limit exceeded",
  "code": "rate_limit",
  "retry_after": 60
}
```
