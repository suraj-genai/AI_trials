from flask import Flask, send_from_directory, jsonify
from routes.chat import chat_bp
from routes.health import health_bp

import os

app = Flask(__name__)

# Register routes
app.register_blueprint(chat_bp, url_prefix='/api')
app.register_blueprint(health_bp, url_prefix='/api')
# Serve Frontend (index.html)
@app.route("/")
def serve_frontend():
    front_end_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../FrontEnd"))
    return send_from_directory(front_end_dir, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True)
