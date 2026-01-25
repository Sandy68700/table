# tracking_server.py
from flask import Flask, request, Response, g, jsonify, render_template_string, send_file
import sqlite3
from datetime import datetime
from urllib.parse import unquote
import os
import io
import pandas as pd

app = Flask(__name__)

# --- Fichiers et base ---
DATA_DIR = "/tmp"  # Render permet seulement /tmp
DB_FILE = os.path.join(DATA_DIR, "opens.db")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.xlsx")

# --- Connexion à SQLite ---
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

# --- Page d'accueil / upload ---
@app.route("/", methods=["GET", "POST"])
def home():
    message = ""
    file_exists = os.path.exists(CONTACTS_FILE)

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file.filename != "":
                file.save(CONTACTS_FILE)
                message = "✅ Fichier contacts.xlsx enregistré avec succès !"
                file_exists = True
            else:
                message = "⚠ Aucun fichier sélectionné."
        else:
            message = "⚠ Clé 'file' manquante."

    html = f"""
    <h1>📊 Serveur de Tracking</h1>
    <p>{message}</p>
    <form method="post" enctype="multipart/form-data">
        <label>Uploader votre fichier contacts.xlsx :</label>
        <input type="file" name="file" accept=".xlsx" required>
        <button type="submit">Uploader</button>
    </form>
    <br>
    {'<a href="/download">⬇ Télécharger contacts.xlsx</a><br><br>' if file_exists else ''}
    <a href="/download_report">⬇ Télécharger le rapport des ouvertures (Excel)</a><br><br>
    <a href="/report">Voir le rapport des ouvertures (HTML)</a><br>
    <a href="/opens">Voir JSON brut des ouvertures</a>
    """
    return render_template_string(html)

# --- Pixel de tracking ---
@app.route("/open/<path:email>")
def track_open(email):
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

# --- JSON brut des ouvertures ---
@app.route("/opens")
def opens():
    db = get_db()
    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY date DESC"
    ).fetchall()
    result = [{"email": r[0], "date": r[1], "ip": r[2], "user_agent": r[3]} for r in rows]
    return jsonify(result)

# --- Rapport HTML ---
@app.route("/report")
def report():
    db = get_db()
    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY date DESC"
    ).fetchall()
    html_rows = ""
    for r in rows:
        html_rows += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    html = f"""
    <h2>📈 Rapport des ouvertures</h2>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr><th>Email</th><th>Date UTC</th><th>IP</th><th>User-Agent</th></tr>
        {html_rows}
    </table>
    <br>
    <a href="/">⬅ Retour</a>
    """
    return render_template_string(html)

# --- Télécharger contacts.xlsx ---
@app.route("/download")
def download_contacts():
    if os.path.exists(CONTACTS_FILE):
        return send_file(CONTACTS_FILE, as_attachment=True)
    else:
        return "⚠ Aucun fichier contacts.xlsx disponible.", 404

# --- Télécharger rapport Excel ---
@app.route("/download_report")
def download_report():
    db = get_db()
    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY date DESC"
    ).fetchall()
    df = pd.DataFrame(rows, columns=["Email", "Date", "IP", "User-Agent"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ouvertures")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="ouvertures.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
