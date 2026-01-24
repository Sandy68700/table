from flask import Flask, request, Response, g, jsonify
import sqlite3
from datetime import datetime
from urllib.parse import unquote

app = Flask(__name__)
DB_FILE = "/tmp/opens.db"  # Render autorise seulement /tmp pour écrire

# --- Connexion à la base SQLite ---
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_FILE)
        db.execute("""
            CREATE TABLE IF NOT EXISTS opens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                date TEXT,
                ip TEXT,
                user_agent TEXT
            )
        """)
        db.commit()
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db:
        db.close()

@app.route("/")
def home():
    return "Serveur de tracking opérationnel ✅"

# --- Pixel de tracking ---
@app.route("/open/<path:email>")
def track_open(email):
    # Décoder l'email encodé
    email = unquote(email)

    db = get_db()
    db.execute(
        "INSERT INTO opens (email, date, ip, user_agent) VALUES (?, ?, ?, ?)",
        (
            email,
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            request.remote_addr,
            request.headers.get("User-Agent", "")
        )
    )
    db.commit()

    # Pixel PNG 1x1 transparent
    pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01' \
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89' \
            b'\x00\x00\x00\nIDATx\xdac`\x00\x00\x00\x02\x00\x01' \
            b'\xe2!\xbc\x33\x00\x00\x00\x00IEND\xaeB`\x82'

    return Response(pixel, mimetype="image/png")

@app.route("/opens")
def opens():
    db = get_db()
    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY date DESC"
    ).fetchall()
    result = [{"email": r[0], "date": r[1], "ip": r[2], "user_agent": r[3]} for r in rows]
    return jsonify(result)
