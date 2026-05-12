"""SQLite connection helpers for Flask request contexts."""

import sqlite3

from flask import g

try:
    from .config import DB_PATH
except ImportError:
    from config import DB_PATH


def connect_db(path=DB_PATH):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def get_db():
    """Return a database connection for the current request context."""
    if 'db' not in g:
        g.db = connect_db()
    return g.db


def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
