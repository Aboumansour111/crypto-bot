from __future__ import annotations

import sqlite3

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION


DB_PATH = settings.db_path

INITIAL_CAPITAL = 100_000_000.0
RISK_PER_TRADE = 0.01
MAX_POSITION_WEIGHT = 0.20
MAX_CONCURRENT_POSITIONS = 5


def create_risk_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS risk_sizing (
            id INTEGER PRIMARY KEY,
            market_id INTEGER NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            strategy_version TEXT NOT NULL,

            rank INTEGER NOT NULL,
            signal TEXT NOT NULL,
            score REAL NOT NULL,

            capital REAL NOT NULL,
            risk_amount REAL NOT NULL,

            entry_price REAL,
            stop_loss REAL,

            stop_distance REAL,
            stop_distance_pct REAL,

            position_size REAL,
            position_value REAL,
            position_weight REAL,

            risk_per_unit REAL,
            actual_risk REAL,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(market_id) REFERENCES markets(id),

            UNIQUE(
                market_id,
                timeframe,
                timestamp,
                strategy_version
            )
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_risk_tf_ts
        ON risk_sizing(timeframe, timestamp)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_risk_signal
        ON risk_sizing(timeframe, timestamp, signal)
    """)

    conn.commit()


def build_risk(
    timeframe: str,
    strategy_version: str = STRATEGY_VERSION,
    capital: float = INITIAL_CAPITAL,
) -> int:

    if timeframe not in ("1D", "4h"):
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    if capital <= 0:
        raise ValueError("capital must be positive")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    create_risk_table(conn)

    conn.execute(
        """
        DELETE FROM risk_sizing
        WHERE timeframe=?
          AND strategy_version=?
        """,
        (timeframe, strategy_version),
    )

    rows = conn.execute(
        """
        SELECT
            s.market_id,
            s.timeframe,
            s.timestamp,
            s.strategy_version,
            s.rank,
            s.signal,
            s.score,
            s.entry_price,
            s.stop_loss
        FROM signals s
        WHERE s.timeframe=?
          AND s.strategy_version=?
        ORDER BY s.timestamp, s.rank
        """,
        (timeframe, strategy_version),
    ).fetchall()

    insert_sql = """
        INSERT INTO risk_sizing (
            market_id,
            timeframe,
            timestamp,
            strategy_version,
            rank,
            signal,
            score,
            capital,
            risk_amount,
            entry_price,
            stop_loss,
            stop_distance,
            stop_distance_pct,
            position_size,
            position_value,
            position_weight,
            risk_per_unit,
            actual_risk
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    output = []

    for row in rows:
        entry = row["entry_price"]
        stop = row["stop_loss"]

        risk_amount = capital * RISK_PER_TRADE

        if (
            row["signal"] == "BUY"
            and entry is not None
            and stop is not None
            and entry > stop > 0
        ):
            stop_distance = float(entry - stop)
            stop_distance_pct = stop_distance / float(entry)

            risk_per_unit = stop_distance

            raw_size = risk_amount / risk_per_unit

            max_position_value = capital * MAX_POSITION_WEIGHT
            max_size = max_position_value / float(entry)

            position_size = min(raw_size, max_size)
            position_value = position_size * float(entry)
            position_weight = position_value / capital
            actual_risk = position_size * risk_per_unit

        else:
            stop_distance = None
            stop_distance_pct = None
            position_size = 0.0
            position_value = 0.0
            position_weight = 0.0
            risk_per_unit = None
            actual_risk = 0.0

        output.append((
            row["market_id"],
            timeframe,
            row["timestamp"],
            strategy_version,
            row["rank"],
            row["signal"],
            row["score"],
            capital,
            risk_amount,
            entry,
            stop,
            stop_distance,
            stop_distance_pct,
            position_size,
            position_value,
            position_weight,
            risk_per_unit,
            actual_risk,
        ))

    conn.executemany(insert_sql, output)
    conn.commit()

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM risk_sizing
        WHERE timeframe=?
          AND strategy_version=?
        """,
        (timeframe, strategy_version),
    ).fetchone()[0]

    conn.close()

    return count
