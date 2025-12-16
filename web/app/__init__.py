from flask import Flask
from flask_restx import Api

api = Api(
    title="Pod Mutating Webhook API",
    version="1.0",
    description="Kubernetes Mutating Admission Webhook for Pod injection",
    doc="/swagger"
)

def create_app():
    app = Flask(__name__)
    
    # Initialize Flask-RESTX
    api.init_app(app)
    
    # Register namespaces (after api is initialized)
    from app.routes import webhook_ns
    api.add_namespace(webhook_ns, path="/")
    
    return app
