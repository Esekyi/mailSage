---
title: Templates
category: API Reference
category_order: 2
order: 3
---

## Email Templates {#email-templates}

Email templates allow you to create reusable email content with dynamic variables. Templates support HTML content and variable substitution using the Jinja2 templating engine.

## Overview {#overview}

- Create and manage reusable email templates
- Support for HTML and plain text content
- Dynamic variable substitution using Jinja2
- Version control for template changes
- Test template rendering before sending

## Template Variables {#template-variables}

Templates use Jinja2 syntax for variable substitution:

```html
<h1>Hello {{ name }}!</h1>
<p>Welcome to {{ company_name }}.</p>
```

Common variable types:

- Text: `{{ user.name }}`
- Numbers: `{{ amount }}`
- Dates: `{{ due_date }}`
- Arrays: `{% for item in items %}`
- Conditionals: `{% if premium_user %}`

## API Reference {#api-reference}

### Create Template

Create a new email template.

#### Endpoint

```http
POST /api/v1/templates
```

#### Headers

```http
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

#### Request Body

```json
{
    "name": "Welcome Email",
    "subject": "Welcome to {{ company_name }}",
    "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our service.</p>",
    "description": "Template for new user welcome emails",
    "variables": ["name", "company_name"],
    "is_active": true
}
```

#### Response

```json
{
    "template": {
        "id": 1,
        "name": "Welcome Email",
        "subject": "Welcome to {{ company_name }}",
        "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our service.</p>",
        "description": "Template for new user welcome emails",
        "variables": ["name", "company_name"],
        "is_active": true,
        "created_at": "2024-01-05T10:30:00Z",
        "updated_at": "2024-01-05T10:30:00Z"
    }
}
```

### List Templates {#list-templates}

Get all templates for your account.

#### Endpoint

```http
GET /api/v1/templates
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | integer | 1 | Page number for pagination |
| per_page | integer | 20 | Items per page |
| search | string | null | Search templates by name |
| is_active | boolean | null | Filter by active status |

#### Response

```json
{
    "templates": [
        {
            "id": 1,
            "name": "Welcome Email",
            "subject": "Welcome to {{ company_name }}",
            "description": "Template for new user welcome emails",
            "is_active": true,
            "created_at": "2024-01-05T10:30:00Z",
            "updated_at": "2024-01-05T10:30:00Z"
        }
    ],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 1,
        "pages": 1
    }
}
```

### Get Template {#get-template}

Get a specific template by ID.

#### Endpoint

```http
GET /api/v1/templates/{template_id}
```

#### Response

```json
{
    "template": {
        "id": 1,
        "name": "Welcome Email",
        "subject": "Welcome to {{ company_name }}",
        "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our service.</p>",
        "description": "Template for new user welcome emails",
        "variables": ["name", "company_name"],
        "is_active": true,
        "created_at": "2024-01-05T10:30:00Z",
        "updated_at": "2024-01-05T10:30:00Z"
    }
}
```

### Update Template {#update-template}

Update an existing template.

#### Endpoint

```http
PUT /api/v1/templates/{template_id}
```

#### Request Body

```json
{
    "name": "Updated Welcome Email",
    "subject": "Welcome to {{ company_name }} - Updated",
    "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our updated service.</p>",
    "description": "Updated welcome email template",
    "variables": ["name", "company_name"],
    "is_active": true
}
```

#### Response

```json
{
    "template": {
        "id": 1,
        "name": "Updated Welcome Email",
        "subject": "Welcome to {{ company_name }} - Updated",
        "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our updated service.</p>",
        "description": "Updated welcome email template",
        "variables": ["name", "company_name"],
        "is_active": true,
        "created_at": "2024-01-05T10:30:00Z",
        "updated_at": "2024-01-05T11:00:00Z"
    }
}
```

### Delete Template {#delete-template}

Delete a template.

#### Endpoint

```http
DELETE /api/v1/templates/{template_id}
```

#### Response

```json
{
    "message": "Template deleted successfully"
}
```

### Test Template {#test-template}

Test template rendering with sample variables.

#### Endpoint

```http
POST /api/v1/templates/{template_id}/test
```

#### Request Body

```json
{
    "variables": {
        "name": "John Doe",
        "company_name": "MailSage"
    }
}
```

#### Response

```json
{
    "subject": "Welcome to MailSage",
    "content": "<h1>Hello John Doe!</h1><p>Welcome to our service.</p>",
    "plain_text": "Hello John Doe!\n\nWelcome to our service."
}
```

## Best Practices {#best-practices}

1. **Variable Naming**
   - Use descriptive variable names
   - Follow snake_case convention
   - Document required variables

2. **Content Structure**
   - Use semantic HTML elements
   - Include both HTML and plain text versions
   - Keep templates modular and reusable

3. **Testing**
   - Test with various variable combinations
   - Verify email client compatibility
   - Check responsive design

4. **Version Control**
   - Keep track of template changes
   - Test updates before activating
   - Archive instead of deleting

## Error Handling {#error-handling}

| Code | Description | Solution |
|------|-------------|----------|
| 400 | Invalid template format | Check HTML syntax and variable names |
| 400 | Missing required variables | Ensure all required variables are provided |
| 404 | Template not found | Verify template ID exists |
| 422 | Template rendering failed | Check variable types and syntax |

## Code Examples {#code-examples}

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

    def create_template(self, name, subject, content, description=None, variables=None):
        response = requests.post(
            f"{self.base_url}/api/v1/templates",
            headers=self.headers,
            json={
                "name": name,
                "subject": subject,
                "content": content,
                "description": description,
                "variables": variables or []
            }
        )
        return response.json()

    def test_template(self, template_id, variables):
        response = requests.post(
            f"{self.base_url}/api/v1/templates/{template_id}/test",
            headers=self.headers,
            json={"variables": variables}
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

    async createTemplate(name, subject, content, description = null, variables = []) {
        const response = await fetch(`${this.baseUrl}/api/v1/templates`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                name,
                subject,
                content,
                description,
                variables
            })
        });
        return response.json();
    }

    async testTemplate(templateId, variables) {
        const response = await fetch(
            `${this.baseUrl}/api/v1/templates/${templateId}/test`,
            {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ variables })
            }
        );
        return response.json();
    }
}
```

## Support {#support}

If you encounter any issues with templates:

- Check our [troubleshooting guide](#error-handling)
- Contact support at <support@mailsage.io>
- Join our [Discord community](https://discord.gg/mailsage)
