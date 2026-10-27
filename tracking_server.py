
import os
import sqlite3
import csv
import io
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import Flask, Response, redirect, render_template_string, request

app = Flask(__name__)

# Configuration
DEMO_URL = os.getenv(
    "DEMO_URL",
    "https://www.youtube.com/watch?v=eHmUDazppV4"
)
SITE_URL = os.getenv(
    "SITE_URL",
    "https://www.alsace-manutention.fr/"
)
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(DATA_DIR, "tracking.db")
)

# Image transparente utilisée pour compter les ouvertures d'emails
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def now_utc():
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables manquantes sans effacer les données existantes."""
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                user_agent TEXT,
                ip TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                clicked_at TEXT NOT NULL,
                destination TEXT,
                user_agent TEXT,
                ip TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                clicked_at TEXT NOT NULL,
                destination TEXT,
                user_agent TEXT,
                ip TEXT
            )
        """)
        conn.commit()


def request_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def log_event(table, email, destination=None):
    if table not in {"opens", "clicks", "site_clicks"}:
        raise ValueError("Table de suivi invalide")

    with db_connect() as conn:
        if table == "opens":
            conn.execute(
                """INSERT INTO opens
                (email, opened_at, user_agent, ip)
                VALUES (?, ?, ?, ?)""",
                (
                    email,
                    now_utc(),
                    request.headers.get("User-Agent", ""),
                    request_ip(),
                ),
            )
        else:
            conn.execute(
                f"""INSERT INTO {table}
                (email, clicked_at, destination, user_agent, ip)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    email,
                    now_utc(),
                    destination or "",
                    request.headers.get("User-Agent", ""),
                    request_ip(),
                ),
            )
        conn.commit()


def safe_site_destination(candidate):
    """Autorise uniquement le domaine configuré pour les redirections."""
    configured = urlparse(SITE_URL)

    if not candidate:
        return SITE_URL

    parsed = urlparse(candidate)

    # Accepte un chemin interne comme /contact/
    if not parsed.scheme and not parsed.netloc:
        path = candidate if candidate.startswith("/") else "/" + candidate
        return f"{configured.scheme}://{configured.netloc}{path}"

    # Accepte uniquement le domaine du site configuré
    if (
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and configured.hostname
        and parsed.hostname.lower() == configured.hostname.lower()
    ):
        return candidate

    return SITE_URL


def email_from_path(value):
    return value.strip() or "unknown"


# --------------------------------------------------
# ROUTES PRINCIPALES
# --------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return redirect("/dashboard", code=302)


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return Response(status=204)


# Compte une ouverture d'email
@app.route("/open/<path:email>", methods=["GET"])
def track_open(email):
    log_event("opens", email_from_path(email))
    return Response(
        PIXEL_GIF,
        mimetype="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"
        },
    )


# Compte un clic vers la démo
@app.route("/click/<path:email>", methods=["GET"])
def track_demo_click(email):
    log_event("clicks", email_from_path(email), DEMO_URL)
    return redirect(DEMO_URL, code=302)


# Compte un clic vers le site Alsace Manutention
# Exemple : /site/contact@exemple.fr
@app.route("/site/<path:email>", methods=["GET"])
def track_site_click(email):
    destination = safe_site_destination(
        request.args.get("url", SITE_URL)
    )
    log_event(
        "site_clicks",
        email_from_path(email),
        destination,
    )
    return redirect(destination, code=302)


# --------------------------------------------------
# TABLEAU DE BORD
# --------------------------------------------------

DASHBOARD_HTML = """
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tableau de suivi des emails</title>
<style>
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 24px;
    background: #f4f6f8;
    color: #20252b;
}
h1 { margin-top: 0; }
.cards {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin: 20px 0;
}
.card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    min-width: 180px;
    box-shadow: 0 2px 8px #0001;
}
.number {
    font-size: 2rem;
    font-weight: bold;
    margin-top: 8px;
}
table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    margin: 16px 0 28px;
}
th, td {
    padding: 10px;
    text-align: left;
    border-bottom: 1px solid #e2e5e8;
    overflow-wrap: anywhere;
}
th { background: #e9edf1; }
a { color: #075eb5; }
.links {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    margin: 18px 0;
}
.muted { color: #5d6670; }
</style>
</head>
<body>
<h1>Tableau de suivi des emails</h1>
<p class="muted">
Les ouvertures et clics sont enregistrés en UTC.
Les outils de confidentialité des emails peuvent fausser les ouvertures.
</p>

<div class="cards">
    <div class="card">
        <div>Ouvertures d'emails</div>
        <div class="number">{{ opens_count }}</div>
    </div>
    <div class="card">
        <div>Clics sur la démo</div>
        <div class="number">{{ clicks_count }}</div>
    </div>
    <div class="card">
        <div>Clics vers le site</div>
        <div class="number">{{ site_clicks_count }}</div>
    </div>
</div>

<div class="links">
    <a href="/report">Exporter les ouvertures (CSV)</a>
    <a href="/click_report">Exporter les clics démo (CSV)</a>
    <a href="/site_click_report">Exporter les clics site (CSV)</a>
</div>

<h2>Dernières ouvertures</h2>
<table>
<thead><tr>
<th>Date UTC</th><th>Email / identifiant</th>
<th>Adresse IP</th><th>Navigateur</th>
</tr></thead>
<tbody>
{% for row in opens %}
<tr>
<td>{{ row["opened_at"] }}</td>
<td>{{ row["email"] }}</td>
<td>{{ row["ip"] or "" }}</td>
<td>{{ row["user_agent"] or "" }}</td>
</tr>
{% else %}
<tr><td colspan="4">Aucune ouverture enregistrée.</td></tr>
{% endfor %}
</tbody>
</table>

<h2>Derniers clics vers la démo</h2>
<table>
<thead><tr>
<th>Date UTC</th><th>Email / identifiant</th><th>Destination</th>
</tr></thead>
<tbody>
{% for row in clicks %}
<tr>
<td>{{ row["clicked_at"] }}</td>
<td>{{ row["email"] }}</td>
<td>{{ row["destination"] or "" }}</td>
</tr>
{% else %}
<tr><td colspan="3">Aucun clic démo enregistré.</td></tr>
{% endfor %}
</tbody>
</table>

<h2>Derniers clics vers le site</h2>
<table>
<thead><tr>
<th>Date UTC</th><th>Email / identifiant</th><th>Destination</th>
</tr></thead>
<tbody>
{% for row in site_clicks %}
<tr>
<td>{{ row["clicked_at"] }}</td>
<td>{{ row["email"] }}</td>
<td>{{ row["destination"] or "" }}</td>
</tr>
{% else %}
<tr><td colspan="3">Aucun clic site enregistré.</td></tr>
{% endfor %}
</tbody>
</table>
</body>
</html>
"""


@app.route("/dashboard", methods=["GET"])
def dashboard():
    with db_connect() as conn:
        opens_count = conn.execute(
            "SELECT COUNT(*) FROM opens"
        ).fetchone()[0]
        clicks_count = conn.execute(
            "SELECT COUNT(*) FROM clicks"
        ).fetchone()[0]
        site_clicks_count = conn.execute(
            "SELECT COUNT(*) FROM site_clicks"
        ).fetchone()[0]

        opens = conn.execute(
            "SELECT * FROM opens ORDER BY id DESC LIMIT 100"
        ).fetchall()
        clicks = conn.execute(
            "SELECT * FROM clicks ORDER BY id DESC LIMIT 100"
        ).fetchall()
        site_clicks = conn.execute(
            "SELECT * FROM site_clicks ORDER BY id DESC LIMIT 100"
        ).fetchall()

    return render_template_string(
        DASHBOARD_HTML,
        opens_count=opens_count,
        clicks_count=clicks_count,
        site_clicks_count=site_clicks_count,
        opens=opens,
        clicks=clicks,
        site_clicks=site_clicks,
    )


# --------------------------------------------------
# EXPORTS CSV
# --------------------------------------------------

def csv_response(table, filename):
    if table not in {"opens", "clicks", "site_clicks"}:
        return Response("Table non autorisée", status=400)

    with db_connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY id DESC"
        ).fetchall()

    output = io.StringIO(newline="")
    writer = csv.writer(output)

    if table == "opens":
        writer.writerow([
            "id", "email", "opened_at", "user_agent", "ip"
        ])
        for row in rows:
            writer.writerow([
                row["id"], row["email"], row["opened_at"],
                row["user_agent"], row["ip"]
            ])
    else:
        writer.writerow([
            "id", "email", "clicked_at", "destination",
            "user_agent", "ip"
        ])
        for row in rows:
            writer.writerow([
                row["id"], row["email"], row["clicked_at"],
                row["destination"], row["user_agent"], row["ip"]
            ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
            f'attachment; filename="{filename}"'
        },
    )


@app.route("/report", methods=["GET"])
@app.route("/opens", methods=["GET"])
@app.route("/download", methods=["GET"])
@app.route("/download_report", methods=["GET"])
def opens_report():
    return csv_response("opens", "ouvertures.csv")


@app.route("/click_report", methods=["GET"])
@app.route("/clicks", methods=["GET"])
@app.route("/download_click_report", methods=["GET"])
def clicks_report():
    return csv_response("clicks", "clics_demo.csv")


@app.route("/site_click_report", methods=["GET"])
def site_click_report():
    return csv_response("site_clicks", "clics_site.csv")


# --------------------------------------------------
# ERREURS ET INITIALISATION
# --------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    return "Introuvable", 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Erreur interne du serveur")
    return "Erreur interne du serveur", 500


# Crée les tables manquantes sans effacer les enregistrements existants
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
