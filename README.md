# **📧 Mailsage**

📧 Mailsage is a robust, centralized Email-as-a-Service (EaaS) platform that simplifies email integrations and resource management. This project is designed to provide developers with a seamless API to handle email sending, templates, and API key generation, with role-based access control and customizable resource limits.

---

## **Features**

- **⚡️ Authentication**:

  - User registration, login, and logout.
  - Support for JWT-based authentication.
  - Refresh token mechanism for seamless session management.
  - Email verification required for protected access.

- **🔒 Role-Based Access Control**:

  - Roles: `Free`, `Pro`, `Enterprise`, `Admin`.
  - Role-specific limits on templates, API keys, emails, and webhooks.
  - Admin access for user management and analytics.

- **🌐 Resource Limits**:

  - Enforce limits on:
    - **Templates**: Creation count per role.
    - **Emails**: Daily email sending rate.
    - **API Keys**: Maximum active keys per user role.
    - **Webhooks**: Allowed webhooks for integrations.
    - Template size limits for each role.

- **📧 Email Jobs**:

  - Create and track email sending jobs with limits per role.
  - Manage recipients and monitor usage via analytics.

- **🔐 API Key Management**:

  - Generate, revoke, and manage API keys for user accounts.
  - Secure access to 📧 Mailsage APIs.

- **⚙️ Testing**:

  - Comprehensive test suite for authentication, resource limits, and role enforcement.
  - Verified across scenarios with `pytest`.

---

## **🚀 Installation**

### **⚠️ Prerequisites**

- 👾 Python 3.13 or higher.
- 📈 PostgreSQL database.
- 🌏 Virtual environment for Python (recommended).
- `pip` package manager.

### **📦 Setup**

1. Clone the repository:

   ```bash
   git clone https://github.com/esekyi/mailsage.git
   cd mailsage
   ```

2. Create a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # For macOS/Linux
   venv\Scripts\activate     # For Windows
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up the database:

   ```bash
   flask db upgrade
   ```

5. ▶️ Run the application:

   ```bash
   flask run
   ```

6. ⚡️ Access the app at: `http://127.0.0.1:5000`

---

## **📣 API Endpoints**

### **Authentication**

- **Register**: `/api/v1/auth/register`

  - **Method**: POST
  - **Body**:

    ```json
    {
      "email": "user@example.com",
      "password": "securepassword"
    }
    ```

  - **Response**: `201 Created`

- **Login**: `/api/v1/auth/login`

  - **Method**: POST
  - **Body**:

    ```json
    {
      "email": "user@example.com",
      "password": "securepassword"
    }
    ```

  - **Response**: Access token and refresh token.

- **Refresh Token**: `/api/v1/auth/refresh`

  - **Method**: POST
  - **Body**:

    ```json
    {
      "refresh_token": "your-refresh-token"
    }
    ```

  - **Response**: New access token.

### **Templates**

- **Create Template**: `/api/v1/templates`

  - **Method**: POST
  - **Body**:

    ```json
    {
      "name": "Welcome Email",
      "content": "<h1>Hello, Welcome!</h1>"
    }
    ```

  - **Role Limits**:
    - Free: 5 templates.
    - Pro: 20 templates.
    - Enterprise: Unlimited.

- **Get Templates**: `/api/v1/templates`

  - **Method**: GET

### **API Keys**

- **Generate API Key**: `/api/v1/auth/api-keys`

  - **Method**: POST
  - **Body**:

    ```json
    {
      "name": "My API Key"
    }
    ```

- **Revoke API Key**: `/api/v1/auth/api-keys/<key_id>`

  - **Method**: DELETE

---

## **Testing**

To run the test suite:

1. Activate the virtual environment:

   ```bash
   source venv/bin/activate
   ```

2. Run `pytest`:

   ```bash
   pytest
   ```

3. Example output:

   ```bash
   ========================================================= 28 passed in 3.73s =========================================================
   ```

---

## **🔧 Configuration**

### **Environment Variables**

Set the following environment variables in `.env`:

- `FLASK_APP=app`
- `FLASK_ENV=development`
- `DATABASE_URL=postgresql://username:password@localhost:5432/mailsage`

---

## **⚙️ Future Improvements**

- **Documentation**: Add GitHub Docs-style UI using tools like Docusaurus or MkDocs.
- **Analytics Dashboard**: Provide detailed insights into resource usage and email delivery statistics.
- **Integrations**: Add support for third-party services (e.g., Twilio, AWS SES).
- **Subscription Plans**: Implement payment systems for role upgrades.

---

## **📚 Contributing**

1. Fork the repository.
2. Create a feature branch:

   ```bash
   git checkout -b feature-name
   ```

3. Commit changes:

   ```bash
   git commit -m "Added feature-name"
   ```

4. Push to the branch:

   ```bash
   git push origin feature-name
   ```

5. Open a pull request.

---

## **🔒 License**

This project is licensed under the [MIT License](LICENSE).
