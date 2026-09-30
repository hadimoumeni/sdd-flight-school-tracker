import os

from flask import Flask

from db import init_db

app = Flask(__name__)


@app.route("/")
def health():
    return "Flight School Ops is running"


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
