
# -*- coding: utf-8 -*-

import os
import io
import sqlite3
from datetime import datetime
from html import escape

import pandas as pd
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

app = Flask(__name__)

# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "opens.db")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.xlsx")

DEMO_URL = "https://www.youtube.com/watch?v=eHmUDazppV4"


# ==================================================
# BASE DE DONNÉES
# ==================================================

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

    if db is not None:
        db.close()


def current_timestamp():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def get_activity():
    """Retourne les statistiques et les données regroupées par email."""
    db = get_db()

    total_opens = db.execute(
        "SELECT COUNT(*) FROM opens"
    ).fetchone()[0]

    unique_opens = db.execute(
        "SELECT COUNT(DISTINCT email) FROM opens"
    ).fetchone()[0]

    total_clicks = db.execute(
        "SELECT COUNT(*) FROM clicks"
    ).fetchone()[0]

    unique_clicks = db.execute(
        "SELECT COUNT(DISTINCT email) FROM clicks"
    ).fetchone()[0]

    rows = db.execute("""
        SELECT
            e.email,
            COALESCE(o.open_count, 0),
            o.last_open,
            COALESCE(c.click_count, 0),
            c.last_click
        FROM (
            SELECT email FROM opens
            UNION
            SELECT email FROM clicks
        ) AS e
        LEFT JOIN (
            SELECT email, COUNT(*) AS open_count, MAX(date) AS last_open
            FROM opens
            GROUP BY email
        ) AS o ON o.email = e.email
        LEFT JOIN (
            SELECT email, COUNT(*) AS click_count, MAX(date) AS last_click
            FROM clicks
            GROUP BY email
        ) AS c ON c.email = e.email
        ORDER BY
            COALESCE(c.click_count, 0) DESC,
            COALESCE(o.open_count, 0) DESC,
            e.email ASC
    """).fetchall()

    return total_opens, unique_opens, total_clicks, unique_clicks, rows


# ==================================================
# TABLEAU DE BORD
# URL : /dashboard
# ==================================================

@app.route("/dashboard")
def dashboard():
    total_opens, unique_opens, total_clicks, unique_clicks, rows = (
        get_activity()
    )

    table_rows = ""

    for email, nb_open, last_open, nb_click, last_click in rows:
        safe_email = escape(str(email or ""))
        safe_last_open = escape(str(last_open or "—"))
        safe_last_click = escape(str(last_click or "—"))

        if nb_click > 0:
            status = '<span class="badge clicked">A cliqué sur la démo</span>'
        elif nb_open > 0:
            status = '<span class="badge opened">Ouverture détectée</span>'
        else:
            status = '<span class="badge">Aucune activité</span>'

        table_rows += f"""
        <tr>
            <td>{safe_email}</td>
            <td>{nb_open}</td>
            <td>{safe_last_open}</td>
            <td>{nb_click}</td>
            <td>{safe_last_click}</td>
            <td>{status}</td>
        </tr>
        """

    if not table_rows:
        table_rows = """
        <tr>
            <td colspan="6" class="empty">
                Aucune activité enregistrée pour le moment.
            </td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="60">
        <title>Dashboard - ALSACE MANUTENTION CIBS</title>

        <style>
            * {{ box-sizing: border-box; }}

            body {{
                margin: 0;
                padding: 24px;
                background: #f3f4f6;
                color: #1f2937;
                font-family: Arial, sans-serif;
            }}

            .container {{
                max-width: 1400px;
                margin: auto;
            }}

            h1 {{ color: #1679D3; }}
            h2 {{ font-size: 21px; }}

            .subtitle {{
                color: #6b7280;
                line-height: 1.6;
            }}

            .cards {{
                display: grid;
                grid-template-columns: repeat(4, minmax(0, 1fr));
                gap: 16px;
                margin: 24px 0;
            }}

            .card {{
                background: white;
                padding: 22px;
                border-radius: 12px;
                box-shadow: 0 2px 8px #0000000a;
            }}

            .label {{
                font-size: 13px;
                color: #6b7280;
                line-height: 1.5;
            }}

            .number {{
                margin-top: 12px;
                font-size: 34px;
                font-weight: bold;
            }}

            .blue {{ color: #1679D3; }}
            .green {{ color: #16a34a; }}

            .panel {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                margin-top: 20px;
                box-shadow: 0 2px 8px #0000000a;
            }}

            .table-wrap {{ overflow-x: auto; }}

            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 13px;
            }}

            th, td {{
                padding: 13px 12px;
                text-align: left;
                border-bottom: 1px solid #e5e7eb;
            }}

            th {{
                background: #f9fafb;
                color: #374151;
            }}

            .badge {{
                display: inline-block;
                padding: 6px 9px;
                border-radius: 6px;
                background: #e5e7eb;
                font-size: 12px;
            }}

            .opened {{
                background: #dbeafe;
                color: #1d4ed8;
            }}

            .clicked {{
                background: #dcfce7;
                color: #166534;
            }}

            .links {{
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 18px;
            }}

            .links a {{
                display: inline-block;
                padding: 10px 14px;
                background: #1679D3;
                color: white;
                text-decoration: none;
                border-radius: 7px;
                font-size: 13px;
            }}

            .empty {{
                text-align: center;
                padding: 30px;
                color: #6b7280;
            }}

            .note {{
                margin-top: 20px;
                font-size: 12px;
                line-height: 1.6;
                color: #6b7280;
            }}

            @media (max-width: 900px) {{
                .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            }}

            @media (max-width: 500px) {{
                body {{ padding: 12px; }}
                .cards {{ gap: 10px; }}
                .card {{ padding: 14px; }}
                .number {{ font-size: 28px; }}
            }}
        </style>
    </head>

    <body>
    <div class="container">

        <h1>📊 ALSACE MANUTENTION CIBS</h1>
        <h2>Tableau de bord de la campagne email</h2>

        <p class="subtitle">
            Suivi des ouvertures et des clics sur la démonstration YouTube.
            Actualisation automatique toutes les 60 secondes.
        </p>

        <div class="cards">

            <div class="card">
                <div class="label">Ouvertures enregistrées</div>
                <div class="number blue">{total_opens}</div>
            </div>

            <div class="card">
                <div class="label">Adresses avec ouverture</div>
                <div class="number blue">{unique_opens}</div>
            </div>

            <div class="card">
                <div class="label">Clics sur la démo</div>
                <div class="number green">{total_clicks}</div>
            </div>

            <div class="card">
                <div class="label">Adresses ayant cliqué</div>
                <div class="number green">{unique_clicks}</div>
            </div>

        </div>

        <div class="panel">
            <h2>Activité par contact</h2>

            <div class="table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Ouvertures</th>
                            <th>Dernière ouverture (UTC)</th>
                            <th>Clics démo</th>
                            <th>Dernier clic (UTC)</th>
                            <th>Statut</th>
                        </tr>
                    </thead>

                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>

            <div class="links">
                <a href="/">Accueil</a>
                <a href="/report">Rapport des ouvertures</a>
                <a href="/click_report">Rapport des clics</a>
                <a href="/download_report">Excel ouvertures</a>
                <a href="/download_click_report">Excel clics</a>
            </div>
        </div>

        <p class="note">
            Les ouvertures peuvent être déclenchées automatiquement par
            certaines messageries. Les clics peuvent aussi être vérifiés
            par des systèmes de sécurité. Ces données indiquent des
            événements enregistrés, pas nécessairement des actions humaines.
            Les dates affichées sont en UTC.
        </p>

    </div>
    </body>
    </html>
    """

    return render_template_string(html)


# ==================================================
# PAGE D'ACCUEIL ET IMPORT DES CONTACTS
# ==================================================

@app.route("/", methods=["GET", "POST"])
def home():
    message = ""
    file_exists = os.path.exists(CONTACTS_FILE)

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]

            if file.filename == "":
                message = "Aucun fichier sélectionné."
            elif not file.filename.lower().endswith(".xlsx"):
                message = "Veuillez sélectionner un fichier .xlsx."
            else:
                file.save(CONTACTS_FILE)
                message = "Fichier contacts.xlsx enregistré avec succès."
                file_exists = True
        else:
            message = "Fichier manquant."

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
        <p>{escape(message)}</p>

        <form method="post" enctype="multipart/form-data">
            <label>Importer contacts.xlsx :</label><br><br>
            <input type="file" name="file" accept=".xlsx" required>
            <button type="submit">Uploader</button>
        </form>

        <br>

        {"<a href='/download'>Télécharger contacts.xlsx</a><br><br>" if file_exists else ""}

        <h3>Tableau de bord</h3>
        <a href="/dashboard">Voir le tableau de bord</a>

        <h3>Rapports</h3>
        <a href="/report">Rapport HTML des ouvertures</a><br><br>
        <a href="/opens">Ouvertures au format JSON</a><br><br>
        <a href="/download_report">Télécharger les ouvertures en Excel</a><br><br>

        <a href="/click_report">Rapport HTML des clics</a><br><br>
        <a href="/clicks">Clics au format JSON</a><br><br>
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
# TRACKING DES CLICS SUR LA DÉMO
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

    response = redirect(DEMO_URL, code=302)
    response.headers["Cache-Control"] = "no-store"

    return response


# ==================================================
# DONNÉES JSON DES OUVERTURES
# ==================================================

@app.route("/opens")
def opens():
    db = get_db()

    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY id DESC"
    ).fetchall()

    return jsonify([
        {
            "email": row[0],
            "date": row[1],
            "ip": row[2],
            "user_agent": row[3],
        }
        for row in rows
    ])


# ==================================================
# DONNÉES JSON DES CLICS
# ==================================================

@app.route("/clicks")
def clicks():
    db = get_db()

    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM clicks ORDER BY id DESC"
    ).fetchall()

    return jsonify([
        {
            "email": row[0],
            "date": row[1],
            "ip": row[2],
            "user_agent": row[3],
        }
        for row in rows
    ])


# ==================================================
# RAPPORT HTML DES OUVERTURES
# ==================================================

@app.route("/report")
def report():
    db = get_db()

    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY id DESC"
    ).fetchall()

    table_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row[0] or ''))}</td>"
        f"<td>{escape(str(row[1] or ''))}</td>"
        f"<td>{escape(str(row[2] or ''))}</td>"
        f"<td>{escape(str(row[3] or ''))}</td>"
        "</tr>"
        for row in rows
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"><title>Rapport ouvertures</title></head>
    <body style="font-family:Arial,sans-serif;margin:20px;">
        <h2>Rapport des ouvertures</h2>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr>
                <th>Email</th><th>Date UTC</th><th>IP</th><th>User-Agent</th>
            </tr>
            {table_rows}
        </table>
        <br><a href="/dashboard">Retour au tableau de bord</a>
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
        "SELECT email, date, ip, user_agent FROM clicks ORDER BY id DESC"
    ).fetchall()

    table_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row[0] or ''))}</td>"
        f"<td>{escape(str(row[1] or ''))}</td>"
        f"<td>{escape(str(row[2] or ''))}</td>"
        f"<td>{escape(str(row[3] or ''))}</td>"
        "</tr>"
        for row in rows
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"><title>Rapport clics</title></head>
    <body style="font-family:Arial,sans-serif;margin:20px;">
        <h2>Rapport des clics sur la démo</h2>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr>
                <th>Email</th><th>Date UTC</th><th>IP</th><th>User-Agent</th>
            </tr>
            {table_rows}
        </table>
        <br><a href="/dashboard">Retour au tableau de bord</a>
    </body>
    </html>
    """

    return render_template_string(html)


# ==================================================
# TÉLÉCHARGER CONTACTS EXCEL
# ==================================================

@app.route("/download")
def download_contacts():
    if not os.path.exists(CONTACTS_FILE):
        return "Aucun fichier contacts.xlsx disponible.", 404

    return send_file(
        CONTACTS_FILE,
        as_attachment=True,
        download_name="contacts.xlsx",
    )


# ==================================================
# EXPORT EXCEL DES OUVERTURES
# ==================================================

@app.route("/download_report")
def download_report():
    db = get_db()

    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM opens ORDER BY id DESC"
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
# EXPORT EXCEL DES CLICS
# ==================================================

@app.route("/download_click_report")
def download_click_report():
    db = get_db()

    rows = db.execute(
        "SELECT email, date, ip, user_agent FROM clicks ORDER BY id DESC"
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
