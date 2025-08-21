from app import app
import routes

# Import your google_auth blueprint
from google_auth import google_auth  # adjust import path if needed

# Register google_auth blueprint
app.register_blueprint(google_auth)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
