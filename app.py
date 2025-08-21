import os
import logging
import json
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash

from extensions import db, login_manager, mail, csrf
from models import User, StoreSettings, CartItem, Product

# Optional: nicer CSRF errors + CSRF cookie for AJAX
from flask_wtf.csrf import CSRFError, generate_csrf


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get(
        "SESSION_SECRET",
        "64020109209bdd95191011a66f75925c8a56c82a85b7d67d8452ba9cde73d455",
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True

    # --- Database ---
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///thaavaram.db"
    )
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- Mail (adjust in env or here) ---
    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "")

    # --- CSRF config ---
    app.config["WTF_CSRF_HEADERS"] = ["X-CSRFToken", "X-CSRF-Token"]

    # --- Init extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Login manager config — point to the blueprint route (ensure main.login exists)
    login_manager.login_view = "main.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # User loader (fix deprecation warning)
    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except Exception:
            return None

    # --- Register blueprints ONLY; no duplicate routes here ---
    from routes import main_bp
    app.register_blueprint(main_bp)

    # ⬇️ App-level alias so templates using url_for('index') work
    @app.route("/", endpoint="index")
    def index_alias():
        return redirect(url_for("main.index"))

    # If you use Google OAuth blueprint (optional)
    try:
        from google_auth import google_auth
        app.register_blueprint(google_auth)
    except Exception as e:
        app.logger.info(f"Google auth blueprint not registered: {e}")

    # --- Jinja helpers ---
    @app.template_filter("from_json")
    def from_json_filter(value):
        try:
            return json.loads(value) if value else []
        except Exception:
            return []

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found_error(error):
        try:
            return render_template("errors/404.html"), 404
        except Exception:
            return "404 Not Found", 404

    @app.errorhandler(500)
    def internal_error(error):
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            return "500 Internal Server Error", 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        try:
            return render_template("errors/csrf.html", reason=e.description), 400
        except Exception:
            return f"CSRF Error: {e.description}", 400

    # --- Context processors ---
    @app.context_processor
    def inject_cart_count():
        from flask_login import current_user
        cart_count = 0
        try:
            if getattr(current_user, "is_authenticated", False):
                cart_count = CartItem.query.filter_by(user_id=current_user.id).count()
        except Exception:
            cart_count = 0
        return dict(cart_count=cart_count)

    @app.context_processor
    def inject_settings():
        settings = None
        try:
            settings = StoreSettings.query.first()
        except Exception:
            settings = None
        return dict(store_settings=settings)

    # --- CSRF token cookie for AJAX ---
    @app.after_request
    def set_csrf_cookie(response):
        try:
            if request.method in ("GET", "HEAD", "OPTIONS"):
                token = generate_csrf()
                response.set_cookie(
                    "csrf_token",
                    token,
                    secure=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
                    samesite=os.environ.get("COOKIE_SAMESITE", "Lax"),
                    httponly=False,  # JS must read it
                )
        except Exception as e:
            app.logger.debug(f"CSRF cookie set failed: {e}")
        return response

    # --- First-run DB setup / seed ---
    with app.app_context():
        db.create_all()

        # Admin user
        if not User.query.filter_by(email="admin@thaavaram.com").first():
            admin = User(
                username="admin",
                email="admin@thaavaram.com",
                password_hash=generate_password_hash("123"),
                role="admin",
                is_active=True,
            )
            db.session.add(admin)

        # Demo customer
        if not User.query.filter_by(email="customer@test.com").first():
            customer = User(
                username="customer",
                email="customer@test.com",
                password_hash=generate_password_hash("123"),
                role="customer",
                is_active=True,
            )
            db.session.add(customer)

        # Store settings
        if not StoreSettings.query.first():
            settings = StoreSettings(
                store_name="Thaavaram",
                store_name_tamil="தாவரம்",
                tagline="Organic Natural Products",
                tagline_tamil="இயற்கையான கேயகம்",
                address="123 Organic Farm Road, Chennai, Tamil Nadu",
                phone="+91 9876543210",
                email="info@thaavaram.com",
                gst_number="33AAAAA0000A1Z5",
                bank_name="Punjab National Bank, MADRAS ANNA NAGAR",
                bank_account_name="sowmiya s",
                bank_account_number="1384000100135482",
                bank_ifsc="PUNB0138400",
                upi_id="dr.sowmiya2112@okaxis",
                free_delivery_amount=500.0,
                delivery_charge=50.0,
                theme_color="#28a745",
                logo_url="/static/images/logo.png",
            )
            db.session.add(settings)

        db.session.commit()
        app.logger.setLevel(logging.INFO)
        app.logger.info("Database initialized successfully")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
