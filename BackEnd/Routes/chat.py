# routes/chat.py
from flask import Blueprint, request, Response, stream_with_context
from core.ai_agent import stream_ai_response, controller

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/stream", methods=["GET"])
def chat_stream():
    user_message = request.args.get("message", "")

    def generate():
        for token in stream_ai_response(user_message):
            yield f"data: {token}\n\n"  # SSE format

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@chat_bp.route("/stop", methods=["POST"])
def stop_generation():
    controller.stop_flag = True
    return {"status": "stopped"}
