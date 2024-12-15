from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.email import EmailJob, EmailDelivery
from app.utils.logging import logger


class MetricsService:
    @staticmethod
    def update_job_metrics(job_id: int) -> bool:
        """Update email campaign metrics for a specific job."""

        try:
            job = EmailJob.query.get(job_id)
            if not job:
                return False

            total_sent = job.success_count + job.failure_count
            if total_sent > 0:
                job.delivery_rate = (job.success_count / total_sent) * 100

            opens = EmailDelivery.query.filter(
                EmailDelivery.job_id == job_id,
                EmailDelivery.opened_at.isnot(None)
            ).count()

            clicks = EmailDelivery.query.filter(
                EmailDelivery.job_id == job_id,
                EmailDelivery.clicked_at.isnot(None)
            ).count()

            if job.success_count > 0:
                job.open_rate = (opens / job.success_count) * 100
                job.click_rate = (clicks / job.success_count) * 100

            db.session.commit()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error updating metrics for job {job_id}: {str(e)}")
            db.session.rollback()
            return False
