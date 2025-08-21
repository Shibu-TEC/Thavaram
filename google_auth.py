# Google OAuth Authentication for Thaavaram
import json
import os
import requests
from extensions import db
from flask import Blueprint, redirect, request, url_for, flash
from flask_login import login_user, logout_user
from models import User
from oauthlib.oauth2 import WebApplicationClient
from werkzeug.security import generate_password_hash

# Check if Google OAuth credentials are available
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Development redirect URL for Replit
if os.environ.get("REPLIT_DEV_DOMAIN"):
    DEV_REDIRECT_URL = f'https://{os.environ["REPLIT_DEV_DOMAIN"]}/google_login/callback'
else:
    DEV_REDIRECT_URL = 'http://localhost:5000/google_login/callback'

# Display setup instructions
if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    print("Google OAuth is configured and ready!")
else:
    print(f"""To enable Google authentication:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID
3. Add {DEV_REDIRECT_URL} to Authorized redirect URIs
4. Provide the Client ID and Client Secret in Replit Secrets

For detailed instructions, see:
https://docs.replit.com/additional-resources/google-auth-in-flask#set-up-your-oauth-app--client
""")

google_auth = Blueprint("google_auth", __name__)

# Initialize OAuth client only if credentials are available
client = None
if GOOGLE_CLIENT_ID:
    client = WebApplicationClient(GOOGLE_CLIENT_ID)

@google_auth.route("/google_login")
def login():
    if not client or not GOOGLE_CLIENT_ID:
        flash('Google login is not configured. Please contact administrator.', 'error')
        return redirect(url_for('login'))
        
    try:
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
            scope=["openid", "email", "profile"],
        )
        return redirect(request_uri)
    except Exception as e:
        flash('Error connecting to Google. Please try again.', 'error')
        return redirect(url_for('login'))

@google_auth.route("/google_login/callback")
def callback():
    if not client or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        flash('Google login is not configured. Please contact administrator.', 'error')
        return redirect(url_for('login'))
        
    try:
        code = request.args.get("code")
        google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url.replace("http://", "https://"),
            redirect_url=request.base_url.replace("http://", "https://"),
            code=code,
        )
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
        )

        client.parse_request_body_response(json.dumps(token_response.json()))

        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        userinfo = userinfo_response.json()
        if userinfo.get("email_verified"):
            users_email = userinfo["email"]
            users_first_name = userinfo.get("given_name", "")
            users_last_name = userinfo.get("family_name", "")
        else:
            flash("User email not available or not verified by Google.", "error")
            return redirect(url_for('login'))

        # Check if user exists
        user = User.query.filter_by(email=users_email).first()
        if not user:
            # Create new user
            user = User(
                username=users_email.split('@')[0],
                email=users_email,
                first_name=users_first_name,
                last_name=users_last_name,
                role='customer'
            )
            # Set a placeholder password hash for Google OAuth users
            user.password_hash = generate_password_hash(f"google_oauth_{users_email}")
            db.session.add(user)
            db.session.commit()
            flash(f'Welcome to Thaavaram, {users_first_name}!', 'success')
        else:
            flash(f'Welcome back, {user.first_name}!', 'success')

        login_user(user)
        return redirect(url_for('index'))
        
    except Exception as e:
        flash('Error during Google authentication. Please try again.', 'error')
        return redirect(url_for('login'))

@google_auth.route("/logout")
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))