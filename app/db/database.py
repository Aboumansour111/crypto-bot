import sqlite3
from pathlib import Path

from app.config.settings import settings


def connect():
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    schema = Path(__file__).with_name("schema.sql").read_text(
        encoding="utf-8"
    )

    with connect() as conn:
        conn.executescript(schema)
        conn.commit()
