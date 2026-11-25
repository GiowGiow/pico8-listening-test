from .pairs import pairs_bp
from .users import users_bp
from .responses import responses_bp

def register_routes(app):
    app.register_blueprint(pairs_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(responses_bp)