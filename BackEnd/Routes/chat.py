# routes/chat.py
from flask import Blueprint, request, Response, stream_with_context, jsonify
from core.ai_agent import agent
import time
import asyncio
chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/chat", methods=["POST"])

def chat_stream():
    """Streaming echo route for testing"""
    data = request.get_json()
    print(f"Received data: {data}")  # DEBUG

    user_message = data.get("message", "")
    date = data.get("date", "")
    def generate():
        try:
            # Create new event loop for this request
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Use the singleton agent instance
            async def run_stream():
                async for token in agent.stream_response(user_message, date):
                    yield f"data: {token}\n\n"
                yield "data: [DONE]\n\n"

                # Execute the async generator

            async_gen = run_stream()

            while True:
                try:
                    token = loop.run_until_complete(async_gen.__anext__())
                    yield token
                except StopAsyncIteration:
                    break

            loop.close()

        except Exception as e:
            print(f"Error in generate: {e}")
            yield f"data: Error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )
@chat_bp.route("/messages", methods=["GET"])
def get_messages():
    """Dummy endpoint for now"""
    return jsonify({"messages": []})
#
#
# @chat_bp.route("/stop", methods=["POST"])
# def stop_generation():
#     controller.stop_flag = True
#     return {"status": "stopped"}
