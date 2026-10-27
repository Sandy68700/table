
# -*- coding: utf-8 -*-

import os
import io
import sqlite3
import logging
from datetime import datetime, timezone
from urllib.parse import unquote

import pandas as pd
from flask import (
    Flask,
    request,
    Response,
    redirect,
    jsonify,
    render_template_string,
    send_file,
    g,
)
from werkzeug.utils import secure_filename


# ============================================================
# CONFIGURATION
# ============================================================

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Sur Render, DATA_DIR peut être défini sur le chemin
# d'un disque persistant, par exemple /var/data.
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(BASE_DIR, "data")
)

os.makedirs(DATA_DIR, exist_ok=True)

DB_FILE = os.path.join(DATA_DIR, "opens.db")
CONTACTS_FILE = os.path.join(DATA_DIR, "contacts.xlsx")

DEMO_URL = "https://www.youtube.com/watch?v=eHmUDazppV4"

# Image PNG transparente de 1 x 1 pixel
TRACKING_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\x0f"
    b"\x00\x01\x01\x01\x00\x18\xdd\x8d\xb0"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    """Retourne une connexion SQLite pour la requête en cours."""
    if "_database" not in g:
        db = sqlite3.connect(DB_FILE)
        db.row_factory = sqlite3.Row

        db.execute("""
            CREATE TABLE IF NOT EXISTS opens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                date TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                date TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT
            )
        """)

        db.commit()
        g._database = db

    return g._database


@app.teardown_appcontext
def close_connection(exception=None):
    """Ferme la connexion SQLite à la fin de la requête."""
    db = g.pop("_database", None)

    if db is not None:
        db.close()


def init_db():
    """Crée les tables au démarrage si elles n'existent pas."""
    db = sqlite3.connect(DB_FILE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS opens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            date TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            date TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT
        )
    """)

    db.commit()
    db.close()


def current_timestamp():
    """Date et heure UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def normalize_email(email):
    """Normalise l'adresse reçue dans l'URL."""
    return unquote(email).strip()


def record_event(table, email):
    """Enregistre une ouverture ou un clic."""
    if table not in ("opens", "clicks"):
        raise ValueError("Type d'événement invalide")

    email = normalize_email(email)

    db = get_db()
    db.execute(
        f"""
        INSERT INTO {table} (email, date, ip, user_agent)
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            current_timestamp(),
            request.headers.get("X-Forwarded-For", request.remote_addr),
            request.headers.get("User-Agent", ""),
        ),
    )
    db.commit()


def fetch_all(query, params=()):
    """Exécute une requête de lecture et renvoie les résultats."""
    db = get_db()
    return db.execute(query, params).fetchall()


# Initialisation des tables au démarrage
init_db()


# ============================================================
# HOME PAGE / CONTACTS
# ============================================================

@app.route("/", methods=["GET", "POST"])
def home():
    message = ""

    if request.method == "POST":
        uploaded_file = (
            request.files.get("file")
            or request.files.get("contacts_file")
        )

        if not uploaded_file or not uploaded_file.filename:
            message = "Sélectionne un fichier Excel à importer."
        elif not uploaded_file.filename.lower().endswith(".xlsx"):
            message = "Le fichier doit être au format .xlsx."
        else:
            try:
                uploaded_file.save(CONTACTS_FILE)
                message = "Le fichier contacts.xlsx a été importé."
            except Exception:
                app.logger.exception("Erreur lors de l'import des contacts")
                message = "Impossible d'enregistrer le fichier."

    contacts_exists = os.path.exists(CONTACTS_FILE)

    return render_template_string("""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Suivi des campagnes email</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 40px auto;
                padding: 0 18px;
                color: #222;
            }
            a, button {
                display: inline-block;
                margin: 6px 4px 6px 0;
                padding: 11px 15px;
                background: #174ea6;
                color: white;
                text-decoration: none;
                border: 0;
                border-radius: 5px;
                cursor: pointer;
            }
            input { margin: 12px 0; }
            .message { margin: 16px 0; color: #176b35; }
        </style>
    </head>
    <body>
        <h1>Suivi des campagnes email</h1>

        <p>Gestion des contacts, ouvertures et clics sur le bouton de démonstration.</p>

        {% if message %}
            <p class="message">{{ message }}</p>
        {% endif %}

        <h2>Importer les contacts</h2>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".xlsx" required>
            <button type="submit">Importer le fichier Excel</button>
        </form>

        {% if contacts_exists %}
            <p>Le fichier contacts.xlsx est disponible.</p>
            <a href="/download">Télécharger les contacts</a>
        {% else %}
            <p>Aucun fichier de contacts n'a encore été importé.</p>
        {% endif %}

        <h2>Statistiques</h2>
        <p>
            <a href="/dashboard">Ouvrir le tableau de bord</a>
            <a href="/report">Rapport des ouvertures</a>
            <a href="/click_report">Rapport des clics</a>
        </p>

        <h2>Exports</h2>
        <p>
            <a href="/download_report">Exporter les ouvertures Excel</a>
            <a href="/download_click_report">Exporter les clics Excel</a>
        </p>

        <p>
            <a href="/opens">Données JSON des ouvertures</a>
            <a href="/clicks">Données JSON des clics</a>
        </p>
    </body>
    </html>
    """, message=message, contacts_exists=contacts_exists)


@app.route("/download")
def download_contacts():
    if not os.path.exists(CONTACTS_FILE):
        return "Le fichier contacts.xlsx n'existe pas.", 404

    return send_file(
        CONTACTS_FILE,
        as_attachment=True,
        download_name="contacts.xlsx",
    )


# ============================================================
# TRACKING DES OUVERTURES
# ============================================================

@app.route("/open/<path:email>")
def track_open(email):
    try:
        record_event("opens", email)
    except Exception:
        app.logger.exception("Erreur lors du suivi d'ouverture")
        # Le pixel est tout de même renvoyé pour éviter
        # de casser l'affichage du message dans le client email.

    response = Response(TRACKING_PIXEL, mimetype="image/png")
    response.headers["Cache-Control"] = (
        "no-cache, no-store, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    return response


# ============================================================
# TRACKING DES CLICS
# ============================================================

@app.route("/click/<path:email>")
def track_click(email):
    try:
        record_event("clicks", email)
    except Exception:
        app.logger.exception("Erreur lors du suivi de clic")

    # Destination fixe : on n'utilise pas un paramètre URL fourni
    # par le visiteur, afin d'éviter les redirections non souhaitées.
    return redirect(DEMO_URL, code=302)


# ============================================================
# STATISTIQUES
# ============================================================

def get_activity():
    db = get_db()

    open_total = db.execute(
        "SELECT COUNT(*) FROM opens"
    ).fetchone()[0]

    open_unique = db.execute(
        "SELECT COUNT(DISTINCT email) FROM opens"
    ).fetchone()[0]

    click_total = db.execute(
        "SELECT COUNT(*) FROM clicks"
    ).fetchone()[0]

    click_unique = db.execute(
        "SELECT COUNT(DISTINCT email) FROM clicks"
    ).fetchone()[0]

    rows = db.execute("""
        SELECT
            activity.email,
            COALESCE(o.open_count, 0) AS open_count,
            COALESCE(c.click_count, 0) AS click_count,
            o.last_open,
            c.last_click
        FROM (
            SELECT email FROM opens
            UNION
            SELECT email FROM clicks
        ) AS activity
        LEFT JOIN (
            SELECT email,
                   COUNT(*) AS open_count,
                   MAX(date) AS last_open
            FROM opens
            GROUP BY email
        ) AS o ON o.email = activity.email
        LEFT JOIN (
            SELECT email,
                   COUNT(*) AS click_count,
                   MAX(date) AS last_click
            FROM clicks
            GROUP BY email
        ) AS c ON c.email = activity.email
        ORDER BY click_count DESC, open_count DESC, activity.email ASC
    """).fetchall()

    return {
        "open_total": open_total,
        "open_unique": open_unique,
        "click_total": click_total,
        "click_unique": click_unique,
        "rows": rows,
    }


# ============================================================
# TABLEAU DE BORD
# ============================================================

@app.route("/dashboard")
def dashboard():
    stats = get_activity()

    return render_template_string("""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="60">
        <title>Tableau de bord - Campagne email</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 25px auto;
                padding: 0 15px;
                max-width: 1200px;
                color: #222;
            }
            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
                gap: 15px;
                margin: 24px 0;
            }
            .card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 18px;
                background: #fafafa;
            }
            .number { font-size: 30px; font-weight: bold; margin-top: 8px; }
            .table-wrap { overflow-x: auto; }
            table { border-collapse: collapse; width: 100%; }
            th, td {
                padding: 10px;
                border-bottom: 1px solid #ddd;
                text-align: left;
            }
            th { background: #f0f0f0; }
            a {
                display: inline-block;
                margin: 5px 8px 5px 0;
                color: #174ea6;
            }
        </style>
    </head>
    <body>
        <h1>Tableau de bord de la campagne</h1>
        <p>Actualisation automatique toutes les 60 secondes.</p>

        <nav>
            <a href="/">Accueil</a>
            <a href="/report">Rapport des ouvertures</a>
            <a href="/click_report">Rapport des clics</a>
            <a href="/download_report">Exporter les ouvertures</a>
            <a href="/download_click_report">Exporter les clics</a>
        </nav>

        <div class="cards">
            <div class="card">
                Ouvertures enregistrées
                <div class="number">{{ stats.open_total }}</div>
            </div>
            <div class="card">
                Adresses avec au moins une ouverture
                <div class="number">{{ stats.open_unique }}</div>
            </div>
            <div class="card">
                Clics enregistrés
                <div class="number">{{ stats.click_total }}</div>
            </div>
            <div class="card">
                Adresses avec au moins un clic
                <div class="number">{{ stats.click_unique }}</div>
            </div>
        </div>

        <h2>Résultats par adresse email</h2>

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Adresse email</th>
                        <th>Ouvertures</th>
                        <th>Clics</th>
                        <th>Dernière ouverture</th>
                        <th>Dernier clic</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in stats.rows %}
                    <tr>
                        <td>{{ row["email"] }}</td>
                        <td>{{ row["open_count"] }}</td>
                        <td>{{ row["click_count"] }}</td>
                        <td>{{ row["last_open"] or "—" }}</td>
                        <td>{{ row["last_click"] or "—" }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5">Aucune activité enregistrée.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <p>
            Remarque : les systèmes de protection des emails peuvent déclencher
            des ouvertures automatiques. Une ouverture ne prouve donc pas
            toujours qu'une personne a lu le message.
        </p>
    </body>
    </html>
    """, stats=stats)


# ============================================================
# RAPPORTS DES OUVERTURES
# ============================================================

@app.route("/opens")
def opens():
    rows = fetch_all("""
        SELECT id, email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
    """)

    return jsonify([dict(row) for row in rows])


@app.route("/report")
def report():
    rows = fetch_all("""
        SELECT id, email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
    """)

    return render_template_string("""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Rapport des ouvertures</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 25px; }
            table { border-collapse: collapse; width: 100%; }
            th, td {
                padding: 9px;
                border: 1px solid #ddd;
                text-align: left;
                overflow-wrap: anywhere;
            }
            th { background: #f0f0f0; }
            .table-wrap { overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>Rapport des ouvertures</h1>
        <p><a href="/dashboard">Retour au tableau de bord</a></p>
        <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Email</th>
                    <th>Date</th>
                    <th>Adresse IP</th>
                    <th>Navigateur</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    <td>{{ row["id"] }}</td>
                    <td>{{ row["email"] }}</td>
                    <td>{{ row["date"] }}</td>
                    <td>{{ row["ip"] or "" }}</td>
                    <td>{{ row["user_agent"] or "" }}</td>
                </tr>
                {% else %}
                <tr><td colspan="5">Aucune ouverture enregistrée.</td></tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
    </body>
    </html>
    """, rows=rows)


# ============================================================
# RAPPORTS DES CLICS
# ============================================================

@app.route("/clicks")
def clicks():
    rows = fetch_all("""
        SELECT id, email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
    """)

    return jsonify([dict(row) for row in rows])


@app.route("/click_report")
def click_report():
    rows = fetch_all("""
        SELECT id, email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
    """)

    return render_template_string("""
    <!doctype html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Rapport des clics</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 25px; }
            table { border-collapse: collapse; width: 100%; }
            th, td {
                padding: 9px;
                border: 1px solid #ddd;
                text-align: left;
                overflow-wrap: anywhere;
            }
            th { background: #f0f0f0; }
            .table-wrap { overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>Rapport des clics sur la démonstration</h1>
        <p><a href="/dashboard">Retour au tableau de bord</a></p>
        <p>
            Destination du bouton :
            <a href="{{ demo_url }}" target="_blank" rel="noopener noreferrer">
                Voir la vidéo YouTube
            </a>
        </p>
        <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Email</th>
                    <th>Date</th>
                    <th>Adresse IP</th>
                    <th>Navigateur</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    <td>{{ row["id"] }}</td>
                    <td>{{ row["email"] }}</td>
                    <td>{{ row["date"] }}</td>
                    <td>{{ row["ip"] or "" }}</td>
                    <td>{{ row["user_agent"] or "" }}</td>
                </tr>
                {% else %}
                <tr><td colspan="5">Aucun clic enregistré.</td></tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
    </body>
    </html>
    """, rows=rows, demo_url=DEMO_URL)


# ============================================================
# EXPORT EXCEL
# ============================================================

def export_excel(query, filename, sheet_name):
    """Crée un fichier Excel en mémoire et le renvoie au navigateur."""
    rows = fetch_all(query)
    dataframe = pd.DataFrame([dict(row) for row in rows])

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(
            writer,
            index=False,
            sheet_name=sheet_name,
        )

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@app.route("/download_report")
def download_report():
    return export_excel(
        """
        SELECT id, email, date, ip, user_agent
        FROM opens
        ORDER BY id DESC
        """,
        "rapport_ouvertures.xlsx",
        "Ouvertures",
    )


@app.route("/download_click_report")
def download_click_report():
    return export_excel(
        """
        SELECT id, email, date, ip, user_agent
        FROM clicks
        ORDER BY id DESC
        """,
        "rapport_clics.xlsx",
        "Clics",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ============================================================
# LOCAL EXECUTION
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
