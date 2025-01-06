from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.job_control_service import JobControlService
from app.models import EmailJob
from app.utils.decorators import require_verified_email
from app.extensions import db

job_control_bp = Blueprint('job_control', __name__, url_prefix='/api/v1/jobs')


@job_control_bp.route('/<int:job_id>/status', methods=['GET'])
@jwt_required()
def get_job_status(job_id: int):
    """Get detailed status of an email job."""
    try:
        # Verify job belongs to user
        job = EmailJob.query.filter_by(
            id=job_id,
            user_id=get_jwt_identity()
        ).first()

        if not job:
            return jsonify({"error": "Job not found"}), 404

        progress = JobControlService.get_job_progress(job_id)
        return jsonify(progress), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@job_control_bp.route('/<int:job_id>/pause', methods=['POST'])
@jwt_required()
@require_verified_email
def pause_job(job_id: int):
    """Pause an ongoing email job."""
    try:
        # Verify job belongs to user
        job = EmailJob.query.filter_by(
            id=job_id,
            user_id=get_jwt_identity()
        ).first()

        if not job:
            return jsonify({"error": "Job not found"}), 404

        if JobControlService.pause_job(job_id):
            return jsonify({"message": "Job paused successfully"}), 200
        return jsonify({"error": "Failed to pause job"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@job_control_bp.route('/<int:job_id>/resume', methods=['POST'])
@jwt_required()
@require_verified_email
def resume_job(job_id: int):
    """Resume a paused email job."""
    try:
        # Verify job belongs to user
        job = EmailJob.query.filter_by(
            id=job_id,
            user_id=get_jwt_identity()
        ).first()

        if not job:
            return jsonify({"error": "Job not found"}), 404

        if JobControlService.resume_job(job_id):
            return jsonify({"message": "Job resumed successfully"}), 200
        return jsonify({"error": "Failed to resume job"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@job_control_bp.route('/<int:job_id>/stop', methods=['POST'])
@jwt_required()
@require_verified_email
def stop_job(job_id: int):
    """Stop an email job."""
    try:
        # Verify job belongs to user
        job = EmailJob.query.filter_by(
            id=job_id,
            user_id=get_jwt_identity()
        ).first()

        if not job:
            return jsonify({"error": "Job not found"}), 404

        reason = request.json.get('reason', 'user_requested')
        if JobControlService.stop_job(job_id, reason):
            return jsonify({"message": "Job stopped successfully"}), 200
        return jsonify({"error": "Failed to stop job"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@job_control_bp.route('/active', methods=['GET'])
@jwt_required()
def get_active_jobs():
    """Get all active jobs for the user."""
    try:
        active_jobs = JobControlService.get_active_jobs(get_jwt_identity())
        return jsonify(active_jobs), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
