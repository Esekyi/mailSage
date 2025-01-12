from enum import Enum
from typing import Dict, Any


class Permission(Enum):
    READ_TEMPLATES = "read_templates"
    WRITE_TEMPLATES = "write_templates"
    DELETE_TEMPLATES = "delete_templates"
    SEND_EMAILS = "send_emails"
    MANAGE_API_KEYS = "manage_api_keys"
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"
    MANAGE_WEBHOOKS = "manage_webhooks"
    ACCESS_ADMIN = "access_admin"
    MANAGE_USERS = "manage_users"
    MANAGE_SMTP = "manage_smtp"


class UserRole(Enum):
    FREE = 'free'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'
    ADMIN = 'admin'


class ResourceLimit(Enum):
    TEMPLATES = "templates"
    API_KEYS = "api_keys"
    DAILY_EMAILS = "daily_emails"
    MONTHLY_EMAILS = "monthly_emails"
    TEMPLATE_SIZE = "template_size"
    MAX_RECIPIENTS = "max_recipients"
    WEBHOOK_ENDPOINTS = "webhook_endpoints"
    SMTPCONFIGS = "smtp_configs"
    DAILY_API_KEY_USAGE = "daily_api_key_usage"


ROLE_CONFIGURATIONS: Dict[str, Dict[str, Any]] = {
    UserRole.FREE.value: {
        'permissions': [
            Permission.READ_TEMPLATES.value,
            Permission.WRITE_TEMPLATES.value,
            Permission.SEND_EMAILS.value,
            Permission.MANAGE_API_KEYS.value,
            Permission.MANAGE_SMTP.value,
        ],
        'limits': {
            ResourceLimit.TEMPLATES.value: 5,
            ResourceLimit.API_KEYS.value: 2,
            ResourceLimit.DAILY_EMAILS.value: 100,
            ResourceLimit.MONTHLY_EMAILS.value: 2_000,
            ResourceLimit.TEMPLATE_SIZE.value: 50_000,  # bytes
            ResourceLimit.MAX_RECIPIENTS.value: 100,  # per batch
            ResourceLimit.WEBHOOK_ENDPOINTS.value: 1,
            ResourceLimit.SMTPCONFIGS.value: 2,
            ResourceLimit.DAILY_API_KEY_USAGE.value: 100,
        },
        'features': ['basic_templates', 'basic_analytics']
    },
    UserRole.PRO.value: {
        'permissions': [
            Permission.READ_TEMPLATES.value,
            Permission.WRITE_TEMPLATES.value,
            Permission.DELETE_TEMPLATES.value,
            Permission.SEND_EMAILS.value,
            Permission.MANAGE_API_KEYS.value,
            Permission.VIEW_ANALYTICS.value,
            Permission.EXPORT_DATA.value,
            Permission.MANAGE_WEBHOOKS.value,
            Permission.MANAGE_SMTP.value,
        ],
        'limits': {
            ResourceLimit.TEMPLATES.value: 50,
            ResourceLimit.API_KEYS.value: 5,
            ResourceLimit.DAILY_EMAILS.value: 2000,
            ResourceLimit.MONTHLY_EMAILS.value: 50_000,
            ResourceLimit.TEMPLATE_SIZE.value: 500_000,  # bytes
            ResourceLimit.MAX_RECIPIENTS.value: 1_000,  # per batch
            ResourceLimit.WEBHOOK_ENDPOINTS.value: 5,
            ResourceLimit.SMTPCONFIGS.value: 10,
            ResourceLimit.DAILY_API_KEY_USAGE.value: 10_000,
        },
        'features': ['advanced_templates', 'advanced_analytics',
                     'priority_support']
    },
    UserRole.ENTERPRISE.value: {
        # All permissions except ADMIN
        'permissions': [p.value for p in Permission if p !=
                        Permission.ACCESS_ADMIN],
        # Unlimited for all resources,
        'limits': {k.value: -1 for k in ResourceLimit},
        'features': ['all']
    },
    UserRole.ADMIN.value: {
        'permissions': [p.value for p in Permission],  # All permissions
        'limits': {k.value: -1 for k in ResourceLimit},  # No limits
        'features': ['all']
    }
}
