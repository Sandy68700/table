import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

from flask import Flask, Response, abort, redirect, render_template_string, request, send_file

app = Flask(__name__)

# Configuration
DEMO_URL = os.getenv("DEMO_URL", "https://www.youtube.com/watch?v=eHmUDazppV4")
SITE_URL = os.getenv("SITE_URL", "https://www.alsace-manutention.fr/")
DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "tracking.db"))

# 1x1 transparent GIF used to track email opens
PIXEL_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
    b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def db_connect():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
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
    # Render may set X-Forwarded-For. Keep only the first address.
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or ""


def log_event(table, email, destination=None):
    if table not in {"opens", "clicks", "site_clicks"}:
        raise ValueError("Invalid tracking table")
    with db_connect() as conn:
        if table == "opens":
            conn.execute(
                "INSERT INTO opens (email, opened_at, user_agent, ip) VALUES (?, ?, ?, ?)",
                (email, now_utc(), request.headers.get("User-Agent", ""), request_ip()),
            )
        else:
            conn.execute(
                f"INSERT INTO {table} (email, clicked_at, destination, user_agent, ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (email, now_utc(), destination or "", request.headers.get("User-Agent", ""), request_ip()),
            )
        conn.commit()


def safe_site_destination(candidate):
    """Only allow redirects to the configured site domain to prevent open redirects."""
    if not candidate:
        return SITE_URL
