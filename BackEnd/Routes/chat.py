# routes/chat.py
from flask import Blueprint, request, Response, jsonify
from core.ai_agent import agent
import json

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat_stream():
    data = request.get_json()
    user_message = data.get("message", "")
    history = data.get("history", [])

    # NEW: Get the accumulated summary context from frontend
    user_context = data.get("context", "")

    def generate():
        # Pass context to the agent
        for chunk_data in agent.stream_response(user_message, history, user_context):
            response_wrapper = {"content": chunk_data}
            yield f"data: {json.dumps(response_wrapper)}\n\n"
        yield "data: {\"done\": true}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@chat_bp.route("/summarize", methods=["POST"])
def summarize_entry():
    data = request.get_json()

    # 1. Get the raw text of today's conversation
    # The frontend must send this text!
    chat_text = data.get("chat_text", "")

    # 2. Get the previous day's summary (if any)
    prev_summary = data.get("previous_summary", "")

    if not chat_text:
        return jsonify({"error": "No chat text provided"}), 400

    # Generate the merged summary
    new_summary = agent.generate_daily_summary(chat_text, prev_summary)

    return jsonify({"summary": new_summary})


@chat_bp.route("/sync", methods=["POST"])
def sync_history():
    """Dummy endpoint to accept frontend sync without error"""
    return jsonify({"status": "synced"}), 200