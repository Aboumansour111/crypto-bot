from __future__ import annotations

import sqlite3

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION


DB_PATH = settings.db_path

SUPPORTED_TIMEFRAMES = ("1D", "4h")

BUY_SCORE = 75.0
WATCH_SCORE = 65.0

STOP_ATR_MULTIPLIER = 1.5
TARGET1_ATR_MULTIPLIER = 2.0
TARGET2_ATR_MULTIPLIER = 3.5


def create_signal_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY,
            market_id INTEGER NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp INTEGER NOT NULL,

            strategy_version TEXT NOT NULL,

            rank INTEGER NOT NULL,
            score REAL NOT NULL,

            signal TEXT NOT NULL,

            entry_price REAL,
            stop_loss REAL,
            target1 REAL,
            target2 REAL,

            risk_pct REAL,
            reward_risk_1 REAL,
            reward_risk_2 REAL,

            atr REAL,
            atr_pct REAL,

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
        CREATE INDEX IF NOT EXISTS idx_signals_tf_ts
        ON signals(timeframe, timestamp)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_signal
        ON signals(timeframe, timestamp, signal)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_signals_rank
        ON signals(timeframe, timestamp, rank)
    """)

    conn.commit()


def build_signals(
    timeframe: str,
    strategy_version: str = STRATEGY_VERSION,
) -> int:

    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    create_signal_table(conn)

    conn.execute(
        """
        DELETE FROM signals
        WHERE timeframe = ?
          AND strategy_version = ?
        """,
        (timeframe, strategy_version),
    )

    rows = conn.execute(
        """
        SELECT
            r.market_id,
            r.timestamp,
            r.rank,
            r.total_score,
            o.close AS close_price,
            f.atr_14,
            f.atr_pct_14
        FROM rankings r
        JOIN features f
          ON f.market_id = r.market_id
         AND f.timeframe = r.timeframe
         AND f.timestamp = r.timestamp
        JOIN ohlcv o
          ON o.market_id = r.market_id
         AND o.timeframe = r.timeframe
         AND o.timestamp = r.timestamp
        WHERE r.timeframe = ?
          AND r.strategy_version = ?
          AND r.selected = 1
        ORDER BY r.timestamp, r.rank
        """,
        (timeframe, strategy_version),
    ).fetchall()

    insert_sql = """
        INSERT INTO signals (
            market_id,
            timeframe,
            timestamp,
            strategy_version,
            rank,
            score,
            signal,
            entry_price,
            stop_loss,
            target1,
            target2,
            risk_pct,
            reward_risk_1,
            reward_risk_2,
            atr,
            atr_pct
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    output = []

    for row in rows:
        score = float(row["total_score"])
        close = row["close_price"]
        atr = row["atr_14"]
        atr_pct = row["atr_pct_14"]

        if close is None or close <= 0:
            signal = "WATCH"
            entry = stop = target1 = target2 = None
            rr1 = rr2 = None

        elif score >= BUY_SCORE and atr is not None and atr > 0:
            signal = "BUY"

            entry = float(close)

            stop = max(
                0.0,
                entry - STOP_ATR_MULTIPLIER * float(atr)
            )

            target1 = (
                entry
                + TARGET1_ATR_MULTIPLIER * float(atr)
            )

            target2 = (
                entry
                + TARGET2_ATR_MULTIPLIER * float(atr)
            )

            risk = entry - stop

            rr1 = (
                (target1 - entry) / risk
                if risk > 0 else None
            )

            rr2 = (
                (target2 - entry) / risk
                if risk > 0 else None
            )

        elif score >= WATCH_SCORE:
            signal = "WATCH"

            entry = float(close)
            stop = target1 = target2 = None
            rr1 = rr2 = None

        else:
            signal = "AVOID"

            entry = float(close)
            stop = target1 = target2 = None
            rr1 = rr2 = None

        output.append((
            row["market_id"],
            timeframe,
            row["timestamp"],
            strategy_version,
            row["rank"],
            score,
            signal,
            entry,
            stop,
            target1,
            target2,
            None,
            rr1,
            rr2,
            float(atr) if atr is not None else None,
            float(atr_pct) if atr_pct is not None else None,
        ))

    conn.executemany(insert_sql, output)
    conn.commit()

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM signals
        WHERE timeframe = ?
          AND strategy_version = ?
        """,
        (timeframe, strategy_version),
    ).fetchone()[0]

    conn.close()

    return count
