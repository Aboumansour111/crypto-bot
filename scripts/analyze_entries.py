import sqlite3
from collections import defaultdict

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION
from app.backtest.engine import run_backtest


DB_PATH = settings.db_path


def analyze(timeframe):

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ---------------------------------------------------------
    # Signals + exact next-bar entry timestamp
    # ---------------------------------------------------------

    rows = conn.execute("""
        SELECT
            s.market_id,
            s.timestamp,
            s.score,
            s.entry_price,
            s.stop_loss,
            s.target1,
            s.target2,

            ss.trend_score,
            ss.momentum_score,
            ss.volume_score,
            ss.volatility_score,
            ss.market_context_score,

            f.rsi_14,
            f.atr_pct_14,
            f.volume_ratio_20,

            mc.market_regime

        FROM signals s

        JOIN strategy_scores ss
          ON ss.market_id = s.market_id
         AND ss.timeframe = s.timeframe
         AND ss.timestamp = s.timestamp
         AND ss.strategy_version = s.strategy_version

        JOIN features f
          ON f.market_id = s.market_id
         AND f.timeframe = s.timeframe
         AND f.timestamp = s.timestamp

        LEFT JOIN market_context mc
          ON mc.timeframe = s.timeframe
         AND mc.timestamp = s.timestamp

        WHERE s.timeframe = ?
          AND s.strategy_version = ?
          AND s.signal = 'BUY'

        ORDER BY s.timestamp
    """, (timeframe, STRATEGY_VERSION)).fetchall()

    # ---------------------------------------------------------
    # Build exact:
    #
    # (market_id, signal_timestamp)
    #             ->
    # next_bar_timestamp
    #
    # This matches the actual backtest entry.
    # ---------------------------------------------------------

    next_bar = {}

    market_ids = sorted({
        r["market_id"]
        for r in rows
    })

    if market_ids:

        placeholders = ",".join(
            "?" for _ in market_ids
        )

        bars = conn.execute(f"""
            SELECT
                market_id,
                timestamp
            FROM ohlcv
            WHERE timeframe = ?
              AND market_id IN ({placeholders})
            ORDER BY market_id, timestamp
        """, [timeframe] + market_ids).fetchall()

        by_market = defaultdict(list)

        for r in bars:
            by_market[r["market_id"]].append(
                r["timestamp"]
            )

        for market_id, timestamps in by_market.items():

            for i in range(len(timestamps) - 1):

                current_ts = timestamps[i]
                following_ts = timestamps[i + 1]

                next_bar[
                    (market_id, current_ts)
                ] = following_ts

    # ---------------------------------------------------------
    # Map actual entry timestamp -> signal
    # ---------------------------------------------------------

    signal_map = {}

    for r in rows:

        entry_time = next_bar.get(
            (r["market_id"], r["timestamp"])
        )

        if entry_time is None:
            continue

        signal_map[
            (r["market_id"], entry_time)
        ] = r

    # ---------------------------------------------------------
    # Backtest
    # ---------------------------------------------------------

    result = run_backtest(timeframe)
    trades = result["trades"]

    print()
    print("=" * 100)
    print(f"ENTRY ANALYSIS — {timeframe}")
    print("=" * 100)

    # ---------------------------------------------------------
    # Score buckets
    # ---------------------------------------------------------

    buckets = defaultdict(lambda: {
        "count": 0,
        "stop": 0,
        "target1": 0,
        "target2": 0,
        "time": 0,
        "final": 0,
        "pnl": 0.0,
    })

    matched = 0
    unmatched = 0

    for trade in trades:

        key = (
            trade["market_id"],
            trade["entry_time"],
        )

        row = signal_map.get(key)

        if row is None:
            unmatched += 1
            continue

        matched += 1

        score = float(row["score"])

        if score < 70:
            bucket = "<70"
        elif score < 75:
            bucket = "70-75"
        elif score < 80:
            bucket = "75-80"
        elif score < 85:
            bucket = "80-85"
        elif score < 90:
            bucket = "85-90"
        elif score < 95:
            bucket = "90-95"
        else:
            bucket = "95-100"

        d = buckets[bucket]

        d["count"] += 1
        d["pnl"] += trade["pnl"]

        if trade["reason"] == "STOP":
            d["stop"] += 1

        elif trade["reason"] == "TARGET1":
            d["target1"] += 1

        elif trade["reason"] == "TARGET2":
            d["target2"] += 1

        elif trade["reason"] == "TIME_EXIT":
            d["time"] += 1

        else:
            d["final"] += 1

    print()
    print("TRADE/SIGNAL MATCH")
    print("-" * 100)
    print(f"Backtest trades : {len(trades):,}")
    print(f"Matched         : {matched:,}")
    print(f"Unmatched       : {unmatched:,}")

    # ---------------------------------------------------------
    # Score buckets
    # ---------------------------------------------------------

    print()
    print("SCORE BUCKETS")
    print("-" * 100)

    print(
        f"{'Score':<12}"
        f"{'Trades':>10}"
        f"{'STOP':>10}"
        f"{'T1':>10}"
        f"{'T2':>10}"
        f"{'TIME':>10}"
        f"{'PnL':>18}"
    )

    order = [
        "<70",
        "70-75",
        "75-80",
        "80-85",
        "85-90",
        "90-95",
        "95-100",
    ]

    for bucket in order:

        d = buckets[bucket]

        print(
            f"{bucket:<12}"
            f"{d['count']:>10,}"
            f"{d['stop']:>10,}"
            f"{d['target1']:>10,}"
            f"{d['target2']:>10,}"
            f"{d['time']:>10,}"
            f"{d['pnl']:>18,.2f}"
        )

    # ---------------------------------------------------------
    # Signal feature distribution
    # ---------------------------------------------------------

    print()
    print("SIGNAL FEATURE DISTRIBUTION")
    print("-" * 100)

    fields = [
        ("score", "Score"),
        ("trend_score", "Trend"),
        ("momentum_score", "Momentum"),
        ("volume_score", "Volume"),
        ("volatility_score", "Volatility"),
        ("market_context_score", "MarketContext"),
        ("rsi_14", "RSI"),
        ("atr_pct_14", "ATR%"),
        ("volume_ratio_20", "VolumeRatio"),
    ]

    for field, label in fields:

        values = [
            float(r[field])
            for r in rows
            if r[field] is not None
        ]

        if not values:
            continue

        avg = sum(values) / len(values)

        print(
            f"{label:<18}"
            f"min={min(values):>10.3f}  "
            f"avg={avg:>10.3f}  "
            f"max={max(values):>10.3f}"
        )

    # ---------------------------------------------------------
    # Market regime
    # ---------------------------------------------------------

    regimes = defaultdict(int)

    for r in rows:
        regimes[
            r["market_regime"] or "UNKNOWN"
        ] += 1

    print()
    print("MARKET REGIME AT ENTRY")
    print("-" * 100)

    for regime, count in sorted(regimes.items()):
        print(
            f"{str(regime):<15}"
            f"{count:>10,}"
        )

    # ---------------------------------------------------------
    # Score thresholds
    # ---------------------------------------------------------

    print()
    print("SIGNAL COUNTS BY SCORE")
    print("-" * 100)

    for threshold in [65, 70, 75, 80, 85, 90, 95]:

        count = sum(
            1
            for r in rows
            if r["score"] >= threshold
        )

        print(
            f"Score >= {threshold:<3}: "
            f"{count:,}"
        )

    conn.close()


def main():

    analyze("1D")
    analyze("4h")


if __name__ == "__main__":
    main()
