"""Almacén propio del gateway (SQLite en el volumen gateway-data).

Guarda cada retiro por su requestId: sirve como clave de idempotencia y como cola
persistente de los retiros aceptados mientras la base legacy está caída.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("GATEWAY_DB", "/app/data/gateway.db")

PENDING, APPLIED, FAILED = "PENDING", "APPLIED", "FAILED"


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _connect() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS retirements ("
            " request_id TEXT PRIMARY KEY, document TEXT NOT NULL, date TEXT NOT NULL,"
            " reason TEXT NOT NULL, consumer TEXT NOT NULL, state TEXT NOT NULL,"
            " movement_id INTEGER, created_at TEXT NOT NULL, applied_at TEXT)"
        )


def get(request_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM retirements WHERE request_id = ?", (request_id,)).fetchone()
    return dict(row) if row else None


def add_pending(request_id, document, date, reason, consumer):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO retirements (request_id, document, date, reason, consumer, state, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_id, document, date, reason, consumer, PENDING, _now()),
        )


def mark(request_id, state, movement_id=None):
    with _connect() as conn:
        conn.execute(
            "UPDATE retirements SET state = ?, movement_id = ?, applied_at = ? WHERE request_id = ?",
            (state, movement_id, _now(), request_id),
        )


def delete(request_id):
    with _connect() as conn:
        conn.execute("DELETE FROM retirements WHERE request_id = ?", (request_id,))


def pending():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM retirements WHERE state = ? ORDER BY created_at", (PENDING,)).fetchall()
    return [dict(r) for r in rows]
