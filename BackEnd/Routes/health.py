from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.route("/healthz")
def health_check():
    """Returns app status"""
    return jsonify({"status": "ok"}), 200
