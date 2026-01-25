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

# --- Page d'accueil ---
@app.route("/")
def home():
    return "Serveur de tracking opérationnel ✅"

# --- Pixel de tracking ---
@app.route("/open/<path:email>")
def track_open(email):
    email = unquote(email)  # décoder l'email encodé

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

# --- Liste JSON des ouvertures ---
@app.route("/opens")
def opens():
    db = get_db()
    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY date DESC"
    ).fetchall()
    result = [{"email": r[0], "date": r[1], "ip": r[2], "user_agent": r[3]} for r in rows]
    return jsonify(result)

# --- Rapport HTML avec taux d'ouverture ---
@app.route("/report")
def report():
    db = get_db()
    rows = db.execute("""
        SELECT email, COUNT(*) as ouvertures, MAX(date) as derniere_ouverture
        FROM opens
        GROUP BY email
        ORDER BY derniere_ouverture DESC
    """).fetchall()

    # Création du tableau HTML
    html = "<h1>📊 Rapport d'ouvertures</h1>"
    html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
    html += "<tr><th>Email</th><th>Nombre d'ouvertures</th><th>Dernière ouverture (UTC)</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>"

    html += "</table><br>"

    # 🔹 Taux d'ouverture (modifie ce nombre selon tes envois)
    total_emails_envoyes = 50  # <-- à adapter pour chaque campagne
    taux_ouverture = (len(rows) / total_emails_envoyes) * 100 if total_emails_envoyes > 0 else 0
    html += f"<p><strong>Taux d'ouverture :</strong> {taux_ouverture:.2f}%</p>"

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
