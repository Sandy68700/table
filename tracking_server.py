from flask import Flask, request, Response, g, jsonify
import sqlite3
from datetime import datetime
from urllib.parse import unquote
import os
import pandas as pd

app = Flask(__name__)
DB_FILE = "/tmp/opens.db"  # Render autorise seulement /tmp pour écrire
CONTACTS_FILE = "/tmp/contacts.xlsx"  # fichier Excel uploadé avec tous les emails

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

# --- Upload du fichier contacts.xlsx ---
@app.route("/upload_contacts", methods=["POST"])
def upload_contacts():
    if "file" not in request.files:
        return "Aucun fichier envoyé", 400

    file = request.files["file"]
    if file.filename == "":
        return "Fichier vide", 400

    file.save(CONTACTS_FILE)
    return "Fichier contacts.xlsx enregistré ✅", 200

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

# --- Rapport HTML avec taux d'ouverture automatique ---
@app.route("/report")
def report():
    db = get_db()

    # Récupération des ouvertures par email
    rows = db.execute("""
        SELECT email, COUNT(*) as ouvertures, MAX(date) as derniere_ouverture
        FROM opens
        GROUP BY email
        ORDER BY derniere_ouverture DESC
    """).fetchall()

    # Tableau HTML
    html = "<h1>📊 Rapport d'ouvertures</h1>"
    html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
    html += "<tr><th>Email</th><th>Nombre d'ouvertures</th><th>Dernière ouverture (UTC)</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td></tr>"

    html += "</table><br>"

    # 🔹 Calcul du taux d'ouverture automatiquement
    emails_ouverts = len(rows)

    # Nombre total d'emails envoyés depuis contacts.xlsx
    if os.path.exists(CONTACTS_FILE):
        try:
            df = pd.read_excel(CONTACTS_FILE)
            total_emails_envoyes = df['Email'].nunique()
        except Exception:
            total_emails_envoyes = emails_ouverts
    else:
        total_emails_envoyes = emails_ouverts

    taux_ouverture = (emails_ouverts / total_emails_envoyes) * 100 if total_emails_envoyes > 0 else 0
    html += f"<p><strong>Taux d'ouverture :</strong> {taux_ouverture:.2f}% ({emails_ouverts}/{total_emails_envoyes})</p>"

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
