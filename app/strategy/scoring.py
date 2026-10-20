from __future__ import annotations

import sqlite3

from app.config.settings import settings


DB_PATH = settings.db_path

STRATEGY_VERSION = "S1_BASE"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_trend(row) -> float:
    score = 0.0

    close = row["close"]
    sma20 = row["sma_20"]
    sma50 = row["sma_50"]
    sma200 = row["sma_200"]
    ema20 = row["ema_20"]
    ema50 = row["ema_50"]

    if close is not None and sma20 is not None:
        score += 20 if close > sma20 else 0

    if close is not None and sma50 is not None:
        score += 20 if close > sma50 else 0

    if close is not None and sma200 is not None:
        score += 20 if close > sma200 else 0

    if ema20 is not None and ema50 is not None:
        score += 20 if ema20 > ema50 else 0

    if sma50 is not None and sma200 is not None:
        score += 20 if sma50 > sma200 else 0

    return score


def score_momentum(row) -> float:
    score = 0.0

    rsi = row["rsi_14"]
    roc7 = row["roc_7"]
    roc14 = row["roc_14"]
    roc30 = row["roc_30"]
    ret7 = row["return_7"]
    ret30 = row["return_30"]

    if rsi is not None:
        if 50 <= rsi <= 70:
            score += 25
        elif 45 <= rsi < 50:
            score += 12
        elif 70 < rsi <= 75:
            score += 15

    if roc7 is not None and roc7 > 0:
        score += 15

    if roc14 is not None and roc14 > 0:
        score += 15

    if roc30 is not None and roc30 > 0:
        score += 15

    if ret7 is not None and ret7 > 0:
        score += 15

    if ret30 is not None and ret30 > 0:
        score += 15

    return clamp(score)


def score_volume(row) -> float:
    ratio = row["volume_ratio_20"]

    if ratio is None:
        return 0.0

    if ratio >= 1.5:
        return 100.0

    if ratio >= 1.2:
        return 80.0

    if ratio >= 1.0:
        return 60.0

    if ratio >= 0.7:
        return 40.0

    return 20.0


def score_volatility(row) -> float:
    atr_pct = row["atr_pct_14"]

    if atr_pct is None:
        return 0.0

    # Prefer moderate volatility.
    if 0.01 <= atr_pct <= 0.04:
        return 100.0

    if 0.04 < atr_pct <= 0.07:
        return 75.0

    if 0.07 < atr_pct <= 0.10:
        return 50.0

    if atr_pct < 0.01:
        return 40.0

    return 20.0


def score_market_context(ctx) -> float:
    if ctx is None:
        return 50.0

    regime = ctx["market_regime"]

    if regime == "BULLISH":
        return 100.0

    if regime == "NEUTRAL":
        return 50.0

    return 0.0


def calculate_total(
    trend: float,
    momentum: float,
    volume: float,
    volatility: float,
    market_context: float,
) -> float:
    """
    S1_BASE weighting.

    Liquidity is intentionally not scored yet because the current
    historical dataset does not contain reliable historical order-book
    depth/spread information.
    """

    return (
        trend * 0.30
        + momentum * 0.30
        + volume * 0.15
        + volatility * 0.10
        + market_context * 0.15
    )


def build_scores(timeframe: str) -> int:
    if timeframe not in ("1D", "4h"):
        raise ValueError("Unsupported timeframe")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            f.*,
            o.close
        FROM features f
        JOIN ohlcv o
          ON o.market_id=f.market_id
         AND o.timeframe=f.timeframe
         AND o.timestamp=f.timestamp
        JOIN markets m
          ON m.id=f.market_id
        WHERE f.timeframe=?
          AND m.quote_symbol='USDT'
          AND m.tradable=1
          AND m.suspended=0
        ORDER BY f.timestamp, f.market_id
        """,
        (timeframe,),
    ).fetchall()

    contexts = {
        row["timestamp"]: row
        for row in conn.execute(
            """
            SELECT *
            FROM market_context
            WHERE timeframe=?
            """,
            (timeframe,),
        ).fetchall()
    }

    count = 0

    for row in rows:
        # Mandatory data for a meaningful score.
        if row["close"] is None:
            continue

        trend = score_trend(row)
        momentum = score_momentum(row)
        volume = score_volume(row)
        volatility = score_volatility(row)
        market_context = score_market_context(
            contexts.get(row["timestamp"])
        )

        total = calculate_total(
            trend,
            momentum,
            volume,
            volatility,
            market_context,
        )

        # Candidate gate:
        # avoid ranking assets with insufficient trend/momentum evidence.
        candidate = int(
            total >= 65
            and trend >= 40
            and momentum >= 40
        )

        conn.execute(
            """
            INSERT INTO strategy_scores (
                market_id,
                timeframe,
                timestamp,
                trend_score,
                momentum_score,
                volume_score,
                volatility_score,
                liquidity_score,
                market_context_score,
                total_score,
                candidate,
                strategy_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(
                market_id,
                timeframe,
                timestamp,
                strategy_version
            )
            DO UPDATE SET
                trend_score=excluded.trend_score,
                momentum_score=excluded.momentum_score,
                volume_score=excluded.volume_score,
                volatility_score=excluded.volatility_score,
                liquidity_score=excluded.liquidity_score,
                market_context_score=excluded.market_context_score,
                total_score=excluded.total_score,
                candidate=excluded.candidate,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                row["market_id"],
                timeframe,
                row["timestamp"],
                trend,
                momentum,
                volume,
                volatility,
                None,
                market_context,
                total,
                candidate,
                STRATEGY_VERSION,
            ),
        )

        count += 1

    conn.commit()
    conn.close()

    return count
