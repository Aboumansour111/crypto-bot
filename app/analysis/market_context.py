from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config.settings import settings


DB_PATH = settings.db_path


def _safe_ratio(numerator, denominator):
    if denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _regime(
    btc_close,
    btc_sma20,
    btc_sma50,
    btc_sma200,
    breadth_sma20,
    breadth_sma50,
    btc_return7,
):
    """
    Conservative market regime classification.

    IMPORTANT:
    Only information available at the current timestamp is used.
    """

    if btc_close is None:
        return "NEUTRAL"

    score = 0

    # BTC trend
    if btc_sma20 is not None:
        score += 1 if btc_close > btc_sma20 else -1

    if btc_sma50 is not None:
        score += 1 if btc_close > btc_sma50 else -1

    if btc_sma200 is not None:
        score += 1 if btc_close > btc_sma200 else -1

    # BTC momentum
    if btc_return7 is not None:
        if btc_return7 > 0.02:
            score += 1
        elif btc_return7 < -0.02:
            score -= 1

    # Market breadth
    if breadth_sma20 is not None:
        if breadth_sma20 >= 0.60:
            score += 1
        elif breadth_sma20 <= 0.40:
            score -= 1

    if breadth_sma50 is not None:
        if breadth_sma50 >= 0.60:
            score += 1
        elif breadth_sma50 <= 0.40:
            score -= 1

    if score >= 3:
        return "BULLISH"

    if score <= -3:
        return "BEARISH"

    return "NEUTRAL"


def build_market_context(timeframe: str) -> int:
    """
    Build market context for every timestamp available in the features table.

    No future data is used:
    each context row reads only feature values at the exact same timestamp.
    """

    if timeframe not in ("1D", "4h"):
        raise ValueError("Unsupported timeframe")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    btc = conn.execute(
        """
        SELECT
            f.timestamp,
            f.rsi_14,
            f.roc_7,
            f.roc_14,
            f.roc_30,
            f.return_1,
            f.return_7,
            f.return_30,
            f.sma_20,
            f.sma_50,
            f.sma_200,
            f.atr_pct_14,
            f.realized_vol_20,
            o.close
        FROM features f
        JOIN markets m ON m.id=f.market_id
        JOIN ohlcv o
          ON o.market_id=f.market_id
         AND o.timeframe=f.timeframe
         AND o.timestamp=f.timestamp
        WHERE f.timeframe=?
          AND m.symbol='BTC_USDT'
        ORDER BY f.timestamp
        """,
        (timeframe,),
    ).fetchall()

    if not btc:
        conn.close()
        raise RuntimeError(f"No BTC feature data for {timeframe}")

    market_rows = conn.execute(
        """
        SELECT
            f.timestamp,
            f.sma_20,
            f.sma_50,
            f.return_7,
            f.return_30,
            f.volume_ratio_20,
            f.realized_vol_20,
            f.atr_pct_14
        FROM features f
        JOIN markets m ON m.id=f.market_id
        WHERE f.timeframe=?
          AND m.quote_symbol='USDT'
          AND m.tradable=1
          AND m.suspended=0
        ORDER BY f.timestamp
        """,
        (timeframe,),
    ).fetchall()

    by_ts = {}

    for row in market_rows:
        ts = row["timestamp"]

        item = by_ts.setdefault(
            ts,
            {
                "total": 0,
                "bull": 0,
                "bear": 0,
                "neutral": 0,
                "sma20_total": 0,
                "sma20_positive": 0,
                "sma50_total": 0,
                "sma50_positive": 0,
                "ret7_total": 0,
                "ret7_positive": 0,
                "ret30_total": 0,
                "ret30_positive": 0,
                "volume_values": [],
                "rv_values": [],
                "atr_values": [],
            },
        )

        sma20 = row["sma_20"]
        sma50 = row["sma_50"]
        ret7 = row["return_7"]
        ret30 = row["return_30"]

        # Individual market direction.
        if sma20 is not None and sma50 is not None:
            item["total"] += 1

            if sma20 > sma50:
                item["bull"] += 1
            elif sma20 < sma50:
                item["bear"] += 1
            else:
                item["neutral"] += 1

        if sma20 is not None:
            item["sma20_total"] += 1
            if row["sma_20"] > 0:
                # Current close is not available here, so this breadth
                # is represented through the feature relationship below.
                pass

        if sma50 is not None:
            item["sma50_total"] += 1

        if ret7 is not None:
            item["ret7_total"] += 1
            if ret7 > 0:
                item["ret7_positive"] += 1

        if ret30 is not None:
            item["ret30_total"] += 1
            if ret30 > 0:
                item["ret30_positive"] += 1

        if row["volume_ratio_20"] is not None:
            item["volume_values"].append(row["volume_ratio_20"])

        if row["realized_vol_20"] is not None:
            item["rv_values"].append(row["realized_vol_20"])

        if row["atr_pct_14"] is not None:
            item["atr_values"].append(row["atr_pct_14"])

    # We need close relative to SMA for true breadth.
    close_rows = conn.execute(
        """
        SELECT
            f.timestamp,
            f.sma_20,
            f.sma_50,
            o.close
        FROM features f
        JOIN markets m ON m.id=f.market_id
        JOIN ohlcv o
          ON o.market_id=f.market_id
         AND o.timeframe=f.timeframe
         AND o.timestamp=f.timestamp
        WHERE f.timeframe=?
          AND m.quote_symbol='USDT'
          AND m.tradable=1
          AND m.suspended=0
        """,
        (timeframe,),
    ).fetchall()

    for row in close_rows:
        item = by_ts.get(row["timestamp"])
        if item is None:
            continue

        close = row["close"]

        if row["sma_20"] is not None and close is not None:
            item.setdefault("close20_total", 0)
            item.setdefault("close20_positive", 0)
            item["close20_total"] += 1

            if close > row["sma_20"]:
                item["close20_positive"] += 1

        if row["sma_50"] is not None and close is not None:
            item.setdefault("close50_total", 0)
            item.setdefault("close50_positive", 0)
            item["close50_total"] += 1

            if close > row["sma_50"]:
                item["close50_positive"] += 1

    inserted = 0

    for row in btc:
        ts = row["timestamp"]
        item = by_ts.get(ts, {})

        volume_values = item.get("volume_values", [])
        rv_values = item.get("rv_values", [])
        atr_values = item.get("atr_values", [])

        breadth20 = _safe_ratio(
            item.get("close20_positive", 0),
            item.get("close20_total", 0),
        )

        breadth50 = _safe_ratio(
            item.get("close50_positive", 0),
            item.get("close50_total", 0),
        )

        positive7 = _safe_ratio(
            item.get("ret7_positive", 0),
            item.get("ret7_total", 0),
        )

        positive30 = _safe_ratio(
            item.get("ret30_positive", 0),
            item.get("ret30_total", 0),
        )

        avg_volume = (
            sum(volume_values) / len(volume_values)
            if volume_values
            else None
        )

        avg_rv = (
            sum(rv_values) / len(rv_values)
            if rv_values
            else None
        )

        avg_atr = (
            sum(atr_values) / len(atr_values)
            if atr_values
            else None
        )

        regime = _regime(
            btc_close=row["close"],
            btc_sma20=row["sma_20"],
            btc_sma50=row["sma_50"],
            btc_sma200=row["sma_200"],
            breadth_sma20=breadth20,
            breadth_sma50=breadth50,
            btc_return7=row["return_7"],
        )

        conn.execute(
            """
            INSERT INTO market_context (
                timeframe,
                timestamp,
                btc_close,
                btc_return_1,
                btc_return_7,
                btc_return_30,
                btc_sma_20,
                btc_sma_50,
                btc_sma_200,
                btc_rsi_14,
                btc_atr_pct_14,
                btc_realized_vol_20,
                total_markets,
                bullish_markets,
                bearish_markets,
                neutral_markets,
                breadth_sma20,
                breadth_sma50,
                breadth_positive_7d,
                breadth_positive_30d,
                avg_volume_ratio_20,
                avg_realized_vol_20,
                avg_atr_pct_14,
                market_regime
            )
            VALUES (
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?
            )
            ON CONFLICT(timeframe, timestamp)
            DO UPDATE SET
                btc_close=excluded.btc_close,
                btc_return_1=excluded.btc_return_1,
                btc_return_7=excluded.btc_return_7,
                btc_return_30=excluded.btc_return_30,
                btc_sma_20=excluded.btc_sma_20,
                btc_sma_50=excluded.btc_sma_50,
                btc_sma_200=excluded.btc_sma_200,
                btc_rsi_14=excluded.btc_rsi_14,
                btc_atr_pct_14=excluded.btc_atr_pct_14,
                btc_realized_vol_20=excluded.btc_realized_vol_20,
                total_markets=excluded.total_markets,
                bullish_markets=excluded.bullish_markets,
                bearish_markets=excluded.bearish_markets,
                neutral_markets=excluded.neutral_markets,
                breadth_sma20=excluded.breadth_sma20,
                breadth_sma50=excluded.breadth_sma50,
                breadth_positive_7d=excluded.breadth_positive_7d,
                breadth_positive_30d=excluded.breadth_positive_30d,
                avg_volume_ratio_20=excluded.avg_volume_ratio_20,
                avg_realized_vol_20=excluded.avg_realized_vol_20,
                avg_atr_pct_14=excluded.avg_atr_pct_14,
                market_regime=excluded.market_regime,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                timeframe,
                ts,
                row["close"],
                row["return_1"],
                row["return_7"],
                row["return_30"],
                row["sma_20"],
                row["sma_50"],
                row["sma_200"],
                row["rsi_14"],
                row["atr_pct_14"],
                row["realized_vol_20"],
                item.get("total", 0),
                item.get("bull", 0),
                item.get("bear", 0),
                item.get("neutral", 0),
                breadth20,
                breadth50,
                positive7,
                positive30,
                avg_volume,
                avg_rv,
                avg_atr,
                regime,
            ),
        )

        inserted += 1

    conn.commit()
    conn.close()

    return inserted
