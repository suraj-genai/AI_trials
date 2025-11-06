from flask import Blueprint, request, jsonify
from core.ai_agent import get_ai_response

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Simple echo route for now"""
    data = request.get_json()
    user_message = data.get("message", "")
    reply = get_ai_response(user_message) #f"AI: You said '{user_message}'"
    return jsonify({"reply": reply})