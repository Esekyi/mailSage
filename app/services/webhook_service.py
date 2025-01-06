from typing import Dict, Any, Optional
import hmac
import hashlib
import json
import requests
from datetime import datetime, timezone
from app.extensions import db
from app.models import Webhook, EmailJob
from app.utils.logging import logger
from flask import current_app


class WebhookService:
    WEBHOOK_TIMEOUT = 5  # seconds
    MAX_RETRIES = 3

    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def create_webhook(user_id: int, url: str, events: list,
                       description: Optional[str] = None) -> Webhook:
        """Create a new webhook endpoint."""
        webhook = Webhook(
            user_id=user_id,
            url=url,
            events=events,
            description=description,
            secret=hashlib.sha256(
                str(datetime.now(timezone.utc).timestamp()).encode()).hexdigest()[:32]
        )
        db.session.add(webhook)
        db.session.commit()
        return webhook

    @staticmethod
    def prepare_payload(event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare webhook payload with standard format."""
        return {
            'event': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': data
        }

    def send_webhook(self, webhook: Webhook, event_type: str,
                     data: Dict[str, Any]) -> bool:
        """Send webhook notification with retry logic."""
        if not webhook.is_active or event_type not in webhook.events:
            return False

        payload = self.prepare_payload(event_type, data)
        payload_json = json.dumps(payload)
        signature = self.generate_signature(payload_json, webhook.secret)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MailSage-Webhook/1.0',
            'X-MailSage-Signature': signature,
            'X-MailSage-Event': event_type,
            'X-Webhook-ID': str(webhook.id)
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.post(
                    webhook.url,
                    data=payload_json,
                    headers=headers,
                    timeout=self.WEBHOOK_TIMEOUT
                )

                response.raise_for_status()

                # Update webhook status
                webhook.last_triggered_at = datetime.now(timezone.utc)
                webhook.failure_count = 0
                db.session.commit()

                return True

            except requests.exceptions.RequestException as e:
                logger.error(f"Webhook delivery failed (attempt {
                             attempt + 1}): {str(e)}")
                webhook.failure_count += 1
                webhook.last_failure_reason = str(e)

                if webhook.failure_count >= 10:  # Disable after 10 consecutive failures
                    webhook.is_active = False
                    logger.warning(
                        f"Webhook {webhook.id} deactivated due to repeated failures")

                db.session.commit()

        return False

    def notify_job_status(self, job_id: int, status: str) -> None:
        """Send webhook notification for job status updates."""
        try:
            job = EmailJob.query.get(job_id)
            if not job:
                return

            user_webhooks = Webhook.query.filter_by(
                user_id=job.user_id,
                is_active=True
            ).all()

            event_type = f"email.job.{status}"
            data = {
                'job_id': job.id,
                'status': job.status,
                'success_count': job.success_count,
                'failure_count': job.failure_count,
                'total_recipients': job.recipient_count,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'template_id': job.template_id,
                'metadata': job.meta_data
            }

            for webhook in user_webhooks:
                self.send_webhook(webhook, event_type, data)

        except Exception as e:
            logger.error(f"Error sending job status webhook: {str(e)}")

    def notify_delivery_status(self, delivery_id: int, status: str) -> None:
        """Send webhook notification for individual delivery updates."""
        try:
            from app.models import EmailDelivery
            delivery = EmailDelivery.query.get(delivery_id)
            if not delivery or not delivery.job:
                return

            user_webhooks = Webhook.query.filter_by(
                user_id=delivery.job.user_id,
                is_active=True
            ).all()

            event_type = f"email.delivery.{status}"
            data = {
                'delivery_id': delivery.id,
                'job_id': delivery.job_id,
                'recipient': delivery.recipient,
                'status': delivery.status,
                'tracking_id': delivery.tracking_id,
                'attempts': delivery.attempts,
                'completed_at': delivery.last_attempt.isoformat() if delivery.last_attempt else None
            }

            for webhook in user_webhooks:
                self.send_webhook(webhook, event_type, data)

        except Exception as e:
            logger.error(f"Error sending delivery status webhook: {str(e)}")
