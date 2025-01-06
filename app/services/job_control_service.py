from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from app.extensions import db, redis_client
from app.models import EmailJob, EmailDelivery
from app.utils.logging import logger
from app.services.webhook_service import WebhookService


class JobControlService:
    """Service for controlling and tracking email jobs."""

    JOB_CONTROL_PREFIX = "email_job_control:"

    def get_job_progress(self, job_id: int, user_id: int) -> Dict[str, Any]:
        """Get detailed progress information for a job."""
        job = EmailJob.query.filter(
            EmailJob.id == job_id,
            EmailJob.user_id == user_id
        ).first()
        if not job:
            raise ValueError("Job not found")

        # Get all deliveries grouped by status
        delivery_stats = db.session.query(
            EmailDelivery.status,
            db.func.count(EmailDelivery.id)
        ).filter_by(job_id=job_id).group_by(EmailDelivery.status).all()

        stats = {status: count for status, count in delivery_stats}
        total = job.recipient_count or 0

        return {
            'id': job.id,
            'status': job.status,
            'tracking_id': job.tracking_id,
            'progress': {
                'total': total,
                'pending': stats.get('pending', 0),
                'sent': stats.get('sent', 0),
                'failed': stats.get('failed', 0),
                'percentage': round((stats.get('sent', 0) / total * 100), 2) if total > 0 else 0
            },
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'is_paused': self.is_job_paused(job_id),
            'template_id': job.template_id,
            'campaign_id': job.campaign_id,
            'meta_data': job.meta_data
        }

    @staticmethod
    def _get_control_key(job_id: int) -> str:
        """Get Redis key for job control."""
        return f"{JobControlService.JOB_CONTROL_PREFIX}{job_id}"

    @staticmethod
    def pause_job(job_id: int, user_id: int) -> bool:
        """Pause an ongoing email job."""
        try:
            job = EmailJob.query.filter(
                EmailJob.id == job_id,
                EmailJob.user_id == user_id
            ).first()
            if not job or job.status not in ['pending', 'processing']:
                return False

            # Set pause flag in Redis
            redis_client.set(
                JobControlService._get_control_key(job_id), 'paused')

            # Update job status
            job.status = 'paused'
            job.meta_data = {
                **(job.meta_data or {}),
                'paused_at': datetime.now(timezone.utc).isoformat(),
                'pause_reason': 'user_requested'
            }
            db.session.commit()

            # Notify via webhook
            webhook_service = WebhookService()
            webhook_service.notify_job_status(job_id, 'paused')

            return True

        except Exception as e:
            logger.error(f"Error pausing job {job_id}: {str(e)}")
            return False

    @staticmethod
    def resume_job(job_id: int, user_id: int) -> bool:
        """Resume a paused email job."""
        try:
            job = EmailJob.query.filter(
                EmailJob.id == job_id,
                EmailJob.user_id == user_id
            ).first()
            if not job or job.status != 'paused':
                return False

            # Remove pause flag
            redis_client.delete(JobControlService._get_control_key(job_id))

            # Update job status
            job.status = 'processing'
            job.meta_data = {
                **(job.meta_data or {}),
                'resumed_at': datetime.now(timezone.utc).isoformat()
            }
            db.session.commit()

            # Requeue remaining deliveries
            from app.tasks.email_tasks import process_email_batch
            process_email_batch.delay(job_id)

            # Notify via webhook
            webhook_service = WebhookService()
            webhook_service.notify_job_status(job_id, 'resumed')

            return True

        except Exception as e:
            logger.error(f"Error resuming job {job_id}: {str(e)}")
            return False

    @staticmethod
    def stop_job(job_id: int, user_id: int, reason: str = 'user_requested') -> bool:
        """Stop an email job (cannot be resumed)."""
        try:
            job = EmailJob.query.filter(
                EmailJob.id == job_id,
                EmailJob.user_id == user_id
            ).first()
            if not job or job.status in ['completed', 'failed', 'stopped']:
                return False

            # Set stop flag
            redis_client.set(
                JobControlService._get_control_key(job_id), 'stopped')

            # Update job status
            job.status = 'stopped'
            job.completed_at = datetime.now(timezone.utc)
            job.meta_data = {
                **(job.meta_data or {}),
                'stopped_at': datetime.now(timezone.utc).isoformat(),
                'stop_reason': reason
            }

            # Mark remaining deliveries as cancelled
            EmailDelivery.query.filter_by(
                job_id=job_id,
                status='pending'
            ).update({
                'status': 'cancelled',
                'error_message': 'Job stopped by user'
            })

            db.session.commit()

            # Notify via webhook
            webhook_service = WebhookService()
            webhook_service.notify_job_status(job_id, 'stopped')

            return True

        except Exception as e:
            logger.error(f"Error stopping job {job_id}: {str(e)}")
            return False

    @staticmethod
    def is_job_paused(job_id: int) -> bool:
        """Check if a job is paused."""
        return redis_client.get(JobControlService._get_control_key(job_id)) == 'paused'

    @staticmethod
    def is_job_stopped(job_id: int) -> bool:
        """Check if a job is stopped."""
        return redis_client.get(JobControlService._get_control_key(job_id)) == 'stopped'

    @staticmethod
    def get_active_jobs(user_id: int) -> List[Dict[str, Any]]:
        """Get all active jobs for a user."""
        active_jobs = EmailJob.query.filter(
            EmailJob.user_id == user_id,
            EmailJob.status.in_(['pending', 'processing', 'paused'])
        ).all()

        return [JobControlService.get_job_progress(job.id, user_id) for job in active_jobs]

    @staticmethod
    def cleanup_stale_jobs() -> int:
        """Clean up jobs that have been stuck in processing state."""
        threshold = datetime.now(timezone.utc) - timedelta(hours=1)
        stale_jobs = EmailJob.query.filter(
            EmailJob.status == 'processing',
            EmailJob.updated_at < threshold
        ).all()

        count = 0
        for job in stale_jobs:
            if JobControlService.stop_job(job.id, reason='stale_job'):
                count += 1

        return count
