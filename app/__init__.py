from flask import Flask, jsonify

from app.config import config_by_name


def create_app(config_name: str = "default") -> Flask:
    """Flask application factory."""
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Register blueprints
    from app.routes.optimize import optimize_bp
    app.register_blueprint(optimize_bp, url_prefix="/api")

    # Generic error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "message": str(e)}), 400

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"error": "Payload too large", "message": "File size exceeds the limit"}), 413

    @app.errorhandler(422)
    def unprocessable_entity(e):
        return jsonify({"error": "Unprocessable entity", "message": str(e)}), 422

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
    
    @app.route('/health')                                                                                                
    def health():                                                                                                      
      return jsonify({"status": "ok"}), 200

    return app
