
# -*- coding: utf-8 -*-

from flask import (
    Flask,
    request,
    Response,
    g,
    jsonify,
    render_template_string,
    send_file,
    redirect,
)
import sqlite3
from datetime import datetime
from urllib.parse import unquote
import os
import io
import pandas as pd

app = Flask(__name__)

# ==================================================
# CONFIGURATION
# ==================================================

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "opens.db")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.xlsx")

# Destination fixe de la démonstration
DEMO_URL = "https://www.youtube.com/watch?v=eHmUDazppV4"


# ==================================================
# BASE DE DONNÉES
# ==================================================

def get_db():
    db = getattr(g, "_database", None)

    if db is None:
        db = g._database = sqlite3.connect(DB_FILE)

        # Table des ouvertures
        db.execute("""
            CREATE TABLE IF NOT EXISTS opens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                date TEXT,
                ip TEXT,
                user_agent TEXT
            )
        """)

        # Table des clics sur la démo
        db.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
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


def current_timestamp():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


# ==================================================
# PAGE D'ACCUEIL
# ==================================================

@app.route("/", methods=["GET", "POST"])
def home():
    message = ""
    file_exists = os.path.exists(CONTACTS_FILE)

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]

            if file.filename != "":
                if not file.filename.lower().endswith(".xlsx"):
                    message = "⚠ Veuillez sélectionner un fichier Excel .xlsx."
                else:
                    file.save(CONTACTS_FILE)
                    message = "Fichier contacts.xlsx enregistré avec succès !"
                    file_exists = True
            else:
                message = "⚠ Aucun fichier sélectionné."
        else:
            message = "⚠ Fichier manquant."

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Serveur de tracking</title>
    </head>
    <body style="font-family:Arial,sans-serif;margin:30px;">

        <h1>📊 Serveur de tracking</h1>

        <p>{message}</p>

        <h3>Contacts</h3>

        <form method="post" enctype="multipart/form-data">
            <label>Importer contacts.xlsx :</label><br><br>
            <input type="file" name="file" accept=".xlsx" required>
            <button type="submit">Uploader</button>
        </form>

        <br>

        {"<a href='/download'>Télécharger contacts.xlsx</a><br><br>" if file_exists else ""}

        <h3>Suivi des ouvertures</h3>
        <a href="/report">Voir le rapport HTML des ouvertures</a><br><br>
        <a href="/opens">Consulter les ouvertures au format JSON</a><br><br>
        <a href="/download_report">Télécharger les ouvertures en Excel</a>

        <h3>Suivi des clics sur la démo</h3>
        <a href="/clicks">Consulter les clics au format JSON</a><br><br>
        <a href="/click_report">Voir le rapport HTML des clics</a><br><br>
        <a href="/download_click_report">Télécharger les clics en Excel</a>

    </body>
    </html>
    """

    return render_template_string(html)


# ==================================================
# TRACKING DES OUVERTURES
# URL : /open/adresse%40exemple.fr
# ==================================================

@app.route("/open/<path:email>")
def track_open(email):
    email = unquote(email)

    db = get_db()

    db.execute(
        """
        INSERT INTO opens (email, date, ip, user_agent)
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            current_timestamp(),
            request.remote_addr,
            request.headers.get("User-Agent", ""),
        ),
    )

    db.commit()

    # Pixel transparent 1 x 1
    pixel = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
        b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
        b'\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\xdac`\x00\x00'
        b'\x00\x02\x00\x01\xe2!\xbc\x33\x00\x00\x00\x00'
        b'IEND\xaeB`\x82'
    )

    response = Response(pixel, mimetype="image/png")
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


# ==================================================
# TRACKING DES CLICS SUR LA DÉMO YOUTUBE
# URL : /click/adresse%40exemple.fr
# ==================================================

@app.route("/click/<path:email>")
def track_click(email):
    email = unquote(email)

    db = get_db()

    db.execute(
        """
        INSERT INTO clicks (email, date, ip, user_agent)
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            current_timestamp(),
            request.remote_addr,
            request.headers.get("User-Agent", ""),
        ),
    )

    db.commit()

    # Redirection vers la vidéo après enregistrement du clic
    response = redirect(DEMO_URL, code=302)
    response.headers["Cache-Control"] = "no-store"

    return response


# ==================================================
# DONNÉES BRUTES DES OUVERTURES
# ==================================================

@app.route("/opens")
def opens():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
        """
    ).fetchall()

    result = [
        {
            "email": row[0],
            "date": row[1],
            "ip": row[2],
            "user_agent": row[3],
        }
        for row in rows
    ]

    return jsonify(result)


# ==================================================
# DONNÉES BRUTES DES CLICS
# ==================================================

@app.route("/clicks")
def clicks():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
        """
    ).fetchall()

    result = [
        {
            "email": row[0],
            "date": row[1],
            "ip": row[2],
            "user_agent": row[3],
        }
        for row in rows
    ]

    return jsonify(result)


# ==================================================
# RAPPORT HTML DES OUVERTURES
# ==================================================

@app.route("/report")
def report():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
        """
    ).fetchall()

    html_rows = ""

    for row in rows:
        html_rows += (
            "<tr>"
            f"<td>{row[0]}</td>"
            f"<td>{row[1]}</td>"
            f"<td>{row[2]}</td>"
            f"<td>{row[3]}</td>"
            "</tr>"
        )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Rapport des ouvertures</title>
    </head>
    <body style="font-family:Arial,sans-serif;margin:20px;">

        <h2>📈 Rapport des ouvertures</h2>

        <table border="1" cellpadding="6" cellspacing="0">
            <tr>
                <th>Email</th>
                <th>Date UTC</th>
                <th>IP</th>
                <th>User-Agent</th>
            </tr>
            {html_rows}
        </table>

        <br><a href="/">Retour à l'accueil</a>

    </body>
    </html>
    """

    return render_template_string(html)


# ==================================================
# RAPPORT HTML DES CLICS
# ==================================================

@app.route("/click_report")
def click_report():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
        """
    ).fetchall()

    html_rows = ""

    for row in rows:
        html_rows += (
            "<tr>"
            f"<td>{row[0]}</td>"
            f"<td>{row[1]}</td>"
            f"<td>{row[2]}</td>"
            f"<td>{row[3]}</td>"
            "</tr>"
        )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Rapport des clics</title>
    </head>
    <body style="font-family:Arial,sans-serif;margin:20px;">

        <h2>🎬 Rapport des clics sur la démo</h2>

        <table border="1" cellpadding="6" cellspacing="0">
            <tr>
                <th>Email</th>
                <th>Date UTC</th>
                <th>IP</th>
                <th>User-Agent</th>
            </tr>
            {html_rows}
        </table>

        <br><a href="/">Retour à l'accueil</a>

    </body>
    </html>
    """

    return render_template_string(html)


# ==================================================
# TÉLÉCHARGER CONTACTS EXCEL
# ==================================================

@app.route("/download")
def download_contacts():
    if os.path.exists(CONTACTS_FILE):
        return send_file(
            CONTACTS_FILE,
            as_attachment=True,
            download_name="contacts.xlsx",
        )

    return "Aucun fichier contacts.xlsx disponible.", 404


# ==================================================
# TÉLÉCHARGER RAPPORT EXCEL DES OUVERTURES
# ==================================================

@app.route("/download_report")
def download_report():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
        """
    ).fetchall()

    df = pd.DataFrame(
        rows,
        columns=["Email", "Date UTC", "IP", "User-Agent"],
    )

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ouvertures")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="ouvertures.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


# ==================================================
# TÉLÉCHARGER RAPPORT EXCEL DES CLICS
# ==================================================

@app.route("/download_click_report")
def download_click_report():
    db = get_db()

    rows = db.execute(
        """
        SELECT email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
        """
    ).fetchall()

    df = pd.DataFrame(
        rows,
        columns=["Email", "Date UTC", "IP", "User-Agent"],
    )

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Clics")

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="clics_demo.xlsx",
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


# ==================================================
# DÉMARRAGE LOCAL
# ==================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
