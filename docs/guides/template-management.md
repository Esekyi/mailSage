---
title: Template Management Guide
category: Guides
category_order: 3
order: 3
---

Learn how to create, manage, and use email templates in MailSage.

## Overview

Email templates in MailSage provide:

- Reusable email content
- Dynamic variable substitution
- Version control
- HTML and plain text support
- Template testing capabilities

## Creating Templates

### Basic Template

Create a simple email template:

```bash
curl -X POST https://api.mailsage.io/api/v1/templates \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Welcome Email",
    "subject": "Welcome to {{ company_name }}",
    "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our service.</p>",
    "description": "Template for new user welcome emails",
    "variables": ["name", "company_name"],
    "is_active": true
  }'
```

### Template Variables

Templates use Jinja2 syntax for variable substitution:

```html
<h1>Hello {{ name }}!</h1>
<p>Welcome to {{ company_name }}.</p>
<p>Your account details:</p>
<ul>
  <li>Email: {{ email }}</li>
  {% if subscription_type %}
  <li>Plan: {{ subscription_type }}</li>
  {% endif %}
</ul>
```

## Managing Templates

### List Templates

Get all available templates:

```bash
curl -X GET https://api.mailsage.io/api/v1/templates \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Update Template

Modify an existing template:

```bash
curl -X PUT https://api.mailsage.io/api/v1/templates/{template_id} \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Welcome Email",
    "subject": "Welcome to {{ company_name }} - Updated",
    "content": "<h1>Hello {{ name }}!</h1><p>Welcome to our updated service.</p>",
    "description": "Updated welcome email template",
    "variables": ["name", "company_name"],
    "is_active": true
  }'
```

### Test Template

Test template rendering with sample variables:

```bash
curl -X POST https://api.mailsage.io/api/v1/templates/{template_id}/test \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "name": "John Doe",
      "company_name": "MailSage"
    }
  }'
```

## Template Features

### Variable Types

1. **Text Variables**

   ```html
   <p>Hello {{ name }}</p>
   ```

2. **Conditional Content**

   ```html
   {% if premium_user %}
   <p>Access premium features</p>
   {% endif %}
   ```

3. **Loops**

   ```html
   <ul>
   {% for item in items %}
     <li>{{ item.name }}: {{ item.value }}</li>
   {% endfor %}
   </ul>
   ```

4. **Filters**

   ```html
   <p>Date: {{ date | date_format }}</p>
   <p>Price: {{ price | currency }}</p>
   ```

### HTML and Plain Text

Templates support both HTML and plain text versions:

```json
{
  "name": "Dual Format Template",
  "content": "<h1>Hello {{ name }}</h1>",
  "plain_text": "Hello {{ name }}",
  "variables": ["name"]
}
```

## Best Practices

1. **Template Organization**
   - Use descriptive template names
   - Document required variables
   - Group related templates
   - Version control changes

2. **Content Structure**
   - Use semantic HTML
   - Include plain text versions
   - Keep templates modular
   - Test responsive design

3. **Variable Management**
   - Use consistent naming
   - Document variable types
   - Provide default values
   - Validate required variables

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

    def create_template(self, name, subject, content, variables=None, description=None):
        data = {
            'name': name,
            'subject': subject,
            'content': content,
            'variables': variables or [],
            'description': description
        }

        response = requests.post(
            f'{self.base_url}/templates',
            headers=self.headers,
            json=data
        )
        return response.json()

    def test_template(self, template_id, variables):
        response = requests.post(
            f'{self.base_url}/templates/{template_id}/test',
            headers=self.headers,
            json={'variables': variables}
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

    async createTemplate(name, subject, content, variables = [], description = null) {
        const data = {
            name,
            subject,
            content,
            variables,
            description
        };

        const response = await fetch(`${this.baseUrl}/templates`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(data)
        });
        return response.json();
    }

    async testTemplate(templateId, variables) {
        const response = await fetch(
            `${this.baseUrl}/templates/${templateId}/test`,
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

## Troubleshooting

### Common Issues

1. **Variable Errors**
   - Missing required variables
   - Incorrect variable names
   - Type mismatches

2. **Rendering Issues**
   - Invalid HTML syntax
   - Broken template logic
   - Missing closing tags

3. **Content Problems**
   - Email client compatibility
   - Responsive design issues
   - Image rendering

### Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `invalid_template` | Template syntax error | Check HTML/variables |
| `missing_variable` | Required variable not provided | Check variable list |
| `render_error` | Template rendering failed | Verify template logic |

## Next Steps

1. [Send emails with templates](../sending-emails)
2. [Set up tracking](../tracking)
3. [Monitor template usage](../analytics)

Need help? Contact [support@mailsage.io](mailto:support@mailsage.io)
