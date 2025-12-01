from flask import Flask, send_from_directory, jsonify
from Routes.chat import chat_bp
from Routes.health import health_bp
import os

app = Flask(__name__)

# Register routes
app.register_blueprint(chat_bp, url_prefix='/api')
app.register_blueprint(health_bp, url_prefix='/api')

# Get frontend directory path
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../FrontEnd"))

# Serve index.html at root
@app.route("/")
def serve_frontend():
    return send_from_directory(FRONTEND_DIR, "index.html")

# Serve all static files (js, css, images, etc.)
@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory(FRONTEND_DIR, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True)