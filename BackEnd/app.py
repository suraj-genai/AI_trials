from flask import Flask
from routes.chat import chat_bp
from routes.health import health_bp

app = Flask(__name__)

# Register routes
app.register_blueprint(chat_bp)
app.register_blueprint(health_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True)
