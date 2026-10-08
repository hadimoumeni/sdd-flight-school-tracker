import os

from flask import Flask, redirect, url_for

from db import init_db
from domains.maintenance.routes import bp as maintenance_bp
from domains.scheduling.routes import bp as scheduling_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.register_blueprint(maintenance_bp)
app.register_blueprint(scheduling_bp)


@app.route("/")
def health():
    return redirect(url_for("maintenance.index"))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
