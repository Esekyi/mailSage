from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app.extensions import db
from app.models import EmailJob, EmailDelivery, Template, SMTPConfiguration
from app.utils.logging import logger


class AnalyticsService:
    """Consolidated analytics service for all metrics."""

    @staticmethod
    def get_email_metrics(user_id: int, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Get comprehensive email sending metrics."""
        query = EmailJob.query.filter_by(user_id=user_id)

        if start_date:
            query = query.filter(EmailJob.created_at >= start_date)
        if end_date:
            query = query.filter(EmailJob.created_at <= end_date)

        total_sent = query.with_entities(
            func.sum(EmailJob.recipient_count)
        ).scalar() or 0

        successful = query.with_entities(
            func.sum(EmailJob.success_count)
        ).scalar() or 0

        failed = query.with_entities(
            func.sum(EmailJob.failure_count)
        ).scalar() or 0

        return {
            'total_sent': total_sent,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total_sent * 100) if total_sent > 0 else 0,
            'failure_rate': (failed / total_sent * 100) if total_sent > 0 else 0
        }

    @staticmethod
    def get_smtp_performance(user_id: int) -> List[Dict[str, Any]]:
        """Get performance metrics for each SMTP configuration."""
        smtp_stats = []

        smtp_configs = SMTPConfiguration.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()

        for config in smtp_configs:
            jobs = EmailJob.query.filter_by(smtp_config_id=config.id)
            total_sent = jobs.with_entities(
                func.sum(EmailJob.recipient_count)
            ).scalar() or 0
            successful = jobs.with_entities(
                func.sum(EmailJob.success_count)
            ).scalar() or 0

            smtp_stats.append({
                'smtp_id': config.id,
                'name': config.name,
                'total_sent': total_sent,
                'successful': successful,
                'success_rate': (successful / total_sent * 100) if total_sent > 0 else 0,
                'failure_count': config.failure_count,
                'last_used': config.last_used_at.isoformat() if config.last_used_at else None
            })

        return smtp_stats

    @staticmethod
    def get_template_usage(user_id: int) -> List[Dict[str, Any]]:
        """Get usage statistics for templates."""
        templates = Template.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()

        template_stats = []
        for template in templates:
            jobs = EmailJob.query.filter_by(template_id=template.id)
            total_uses = jobs.count()
            if total_uses > 0:
                successful = jobs.with_entities(
                    func.sum(EmailJob.success_count)
                ).scalar() or 0
                total_sent = jobs.with_entities(
                    func.sum(EmailJob.recipient_count)
                ).scalar() or 0

                template_stats.append({
                    'template_id': template.id,
                    'name': template.name,
                    'total_uses': total_uses,
                    'total_sent': total_sent,
                    'successful': successful,
                    'success_rate': (successful / total_sent * 100) if total_sent > 0 else 0,
                    'last_used': template.updated_at.isoformat()
                })

        return template_stats

    @staticmethod
    def get_delivery_timeline(user_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily email delivery statistics."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        daily_stats = db.session.query(
            func.date_trunc('day', EmailJob.created_at).label('date'),
            func.sum(EmailJob.recipient_count).label('total_sent'),
            func.sum(EmailJob.success_count).label('successful'),
            func.sum(EmailJob.failure_count).label('failed')
        ).filter(
            EmailJob.user_id == user_id,
            EmailJob.created_at >= start_date,
            EmailJob.created_at <= end_date
        ).group_by(
            func.date_trunc('day', EmailJob.created_at)
        ).order_by(
            func.date_trunc('day', EmailJob.created_at)
        ).all()

        return [{
            'date': stats.date.strftime('%Y-%m-%d'),
            'total_sent': stats.total_sent or 0,
            'successful': stats.successful or 0,
            'failed': stats.failed or 0,
            'success_rate': ((stats.successful or 0) / (stats.total_sent or 1)) * 100
        } for stats in daily_stats]

    @staticmethod
    def get_engagement_metrics(user_id: int) -> Dict[str, Any]:
        """Get email engagement metrics (opens, clicks, etc.)."""
        deliveries = EmailDelivery.query.join(EmailJob).filter(
            EmailJob.user_id == user_id
        )

        total_delivered = deliveries.filter(
            EmailDelivery.status == 'sent'
        ).count()

        if total_delivered == 0:
            return {
                'total_delivered': 0,
                'total_opened': 0,
                'total_clicked': 0,
                'open_rate': 0,
                'click_rate': 0
            }
        total_opened = deliveries.filter(
            EmailDelivery.opened_at.isnot(None)
        ).count()

        total_clicked = deliveries.filter(
            EmailDelivery.clicked_at.isnot(None)
        ).count()

        return {
            'total_delivered': total_delivered,
            'total_opened': total_opened,
            'total_clicked': total_clicked,
            'open_rate': (total_opened / total_delivered) * 100,
            'click_rate': (total_clicked / total_delivered) * 100
        }

    @ staticmethod
    def get_user_dashboard_metrics(user_id: int) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics for a user."""
        try:
            # Get last 30 days metrics
            current_period = AnalyticsService.get_email_metrics(
                user_id,
                start_date=datetime.now(timezone.utc) - timedelta(days=30)
            )

            # Get previous 30 days for comparison
            previous_start = datetime.now(timezone.utc) - timedelta(days=60)
            previous_end = datetime.now(timezone.utc) - timedelta(days=30)
            previous_period = AnalyticsService.get_email_metrics(
                user_id,
                start_date=previous_start,
                end_date=previous_end
            )

            # Calculate changes
            def calculate_change(current: float, previous: float) -> float:
                if previous == 0:
                    return 100 if current > 0 else 0
                return ((current - previous) / previous) * 100

            # Get SMTP health
            smtp_configs = SMTPConfiguration.query.filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            smtp_health = {
                'total_active': len(smtp_configs),
                'healthy': len([s for s in smtp_configs if s.failure_count == 0]),
                'warning': len([s for s in smtp_configs if 0 < s.failure_count <= 3]),
                'critical': len([s for s in smtp_configs if s.failure_count > 3])
            }

            # Get template usage
            template_usage = Template.query.filter_by(
                user_id=user_id,
                is_active=True
            ).join(EmailJob).group_by(Template.id).with_entities(
                Template.id,
                func.count(EmailJob.id).label('usage_count')
            ).all()

            return {
                'current_period': {
                    **current_period,
                    'start_date': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                    'end_date': datetime.now(timezone.utc).isoformat()
                },
                'changes': {
                    'sent': calculate_change(current_period['total_sent'], previous_period['total_sent']),
                    'success_rate': calculate_change(current_period['success_rate'], previous_period['success_rate'])
                },
                'smtp_health': smtp_health,
                'template_stats': {
                    'total_templates': Template.query.filter_by(user_id=user_id, is_active=True).count(),
                    'templates_used': len(template_usage),
                    'most_used': max([t.usage_count for t in template_usage], default=0)
                },
                'engagement': AnalyticsService.get_engagement_metrics(user_id)
            }

        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            raise e
