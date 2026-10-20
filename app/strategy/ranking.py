from __future__ import annotations

import sqlite3

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION


DB_PATH = settings.db_path

# Baseline selection size.
TOP_N = 10
MIN_SCORE = 65.0


def build_rankings(
    timeframe: str,
    top_n: int = TOP_N,
    min_score: float = MIN_SCORE,
) -> int:

    if timeframe not in ("1D", "4h"):
        raise ValueError("Unsupported timeframe")

    if top_n < 1:
        raise ValueError("top_n must be >= 1")

    conn = sqlite3.connect(DB_PATH)

    # Remove previous version only.
    conn.execute(
        """
        DELETE FROM rankings
        WHERE timeframe=?
          AND strategy_version=?
        """,
        (timeframe, STRATEGY_VERSION),
    )

    conn.execute(
        """
        INSERT INTO rankings (
            market_id,
            timeframe,
            timestamp,
            strategy_version,
            total_score,
            rank,
            percentile,
            selected
        )
        SELECT
            market_id,
            timeframe,
            timestamp,
            strategy_version,
            total_score,

            ROW_NUMBER() OVER (
                PARTITION BY timestamp
                ORDER BY
                    total_score DESC,
                    market_id ASC
            ) AS rank,

            PERCENT_RANK() OVER (
                PARTITION BY timestamp
                ORDER BY
                    total_score ASC
            ) AS percentile,

            CASE
                WHEN candidate=1
                 AND total_score >= ?
                 AND ROW_NUMBER() OVER (
                     PARTITION BY timestamp
                     ORDER BY
                         total_score DESC,
                         market_id ASC
                 ) <= ?
                THEN 1
                ELSE 0
            END AS selected

        FROM strategy_scores
        WHERE timeframe=?
          AND strategy_version=?
          AND candidate=1
          AND total_score >= ?
        """,
        (
            min_score,
            top_n,
            timeframe,
            STRATEGY_VERSION,
            min_score,
        ),
    )

    conn.commit()

    count = conn.execute(
        """
        SELECT COUNT(*)
        FROM rankings
        WHERE timeframe=?
          AND strategy_version=?
        """,
        (timeframe, STRATEGY_VERSION),
    ).fetchone()[0]

    conn.close()

    return count
