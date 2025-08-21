# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
from flask import render_template, request, current_app

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()


def init_extensions(app):
    """
    Call this once from your application factory (create_app) to initialize
    all extensions and wire common defaults/handlers.
    """
    # Initialize
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # ---- Login manager defaults ----
    # Use your blueprint-qualified login endpoint
    login_manager.login_view = "main.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"
    # Extra session hardening
    login_manager.session_protection = "strong"

    # ---- CSRF error handler ----
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        # Render a friendly page if you have templates/errors/csrf.html
        try:
            return render_template("errors/csrf.html", reason=e.description), 400
        except Exception:
            # Fallback plain text if template missing
            return ("Bad Request: CSRF token missing or invalid.\n"
                    f"Reason: {e.description}"), 400

    # ---- Set CSRF cookie for JS clients on safe methods ----
    # If you already set a similar after_request in app.py, remove one of them.
    @app.after_request
    def set_csrf_cookie(response):
        # Only set on safe methods to avoid overriding on POST/PUT
        if request.method in ("GET", "HEAD", "OPTIONS"):
            try:
                token = generate_csrf()
                response.set_cookie(
                    "csrf_token",
                    token,
                    # Mirror your session settings
                    secure=app.config.get("SESSION_COOKIE_SECURE", False),
                    samesite=app.config.get("SESSION_COOKIE_SAMESITE", "Lax"),
                    httponly=False,  # must be readable by JS to set X-CSRFToken header
                    path="/",
                )
            except Exception:
                # Do not block the response if cookie set fails
                pass
        return response
