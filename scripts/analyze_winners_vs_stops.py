import sqlite3
from collections import defaultdict

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION
from app.backtest.engine import run_backtest


DB_PATH = settings.db_path


def analyze(timeframe):

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            s.market_id,
            s.timestamp,
            s.score,

            ss.trend_score,
            ss.momentum_score,
            ss.volume_score,
            ss.volatility_score,
            ss.market_context_score,

            f.rsi_14,
            f.atr_pct_14,
            f.volume_ratio_20

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

        WHERE s.timeframe = ?
          AND s.strategy_version = ?
          AND s.signal = 'BUY'
    """, (timeframe, STRATEGY_VERSION)).fetchall()

    # ---------------------------------------------------------
    # Exact signal -> next bar entry timestamp
    # ---------------------------------------------------------

    market_ids = sorted({
        r["market_id"]
        for r in rows
    })

    next_bar = {}

    if market_ids:

        placeholders = ",".join(
            "?" for _ in market_ids
        )

        bars = conn.execute(
            f"""
            SELECT market_id, timestamp
            FROM ohlcv
            WHERE timeframe=?
              AND market_id IN ({placeholders})
            ORDER BY market_id, timestamp
            """,
            [timeframe] + market_ids
        ).fetchall()

        grouped = defaultdict(list)

        for r in bars:
            grouped[r["market_id"]].append(
                r["timestamp"]
            )

        for market_id, timestamps in grouped.items():

            for i in range(len(timestamps) - 1):

                next_bar[
                    (market_id, timestamps[i])
                ] = timestamps[i + 1]

    signal_map = {}

    for r in rows:

        entry_time = next_bar.get(
            (r["market_id"], r["timestamp"])
        )

        if entry_time is not None:
            signal_map[
                (r["market_id"], entry_time)
            ] = r

    # ---------------------------------------------------------
    # Backtest
    # ---------------------------------------------------------

    result = run_backtest(timeframe)

    groups = {
        "STOP": [],
        "TARGET": [],
        "TIME_EXIT": [],
        "FINAL": [],
    }

    for trade in result["trades"]:

        row = signal_map.get(
            (
                trade["market_id"],
                trade["entry_time"],
            )
        )

        if row is None:
            continue

        if trade["reason"] == "STOP":
            group = "STOP"

        elif trade["reason"] in ("TARGET1", "TARGET2"):
            group = "TARGET"

        elif trade["reason"] == "TIME_EXIT":
            group = "TIME_EXIT"

        else:
            group = "FINAL"

        groups[group].append(row)

    # ---------------------------------------------------------
    # Feature averages
    # ---------------------------------------------------------

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

    print()
    print("=" * 110)
    print(f"WINNERS VS STOPS — {timeframe}")
    print("=" * 110)

    print()
    print(
        f"{'Feature':<20}"
        f"{'STOP':>15}"
        f"{'TARGET':>15}"
        f"{'TIME_EXIT':>15}"
        f"{'Difference':>15}"
    )

    print("-" * 110)

    for field, label in fields:

        values = {}

        for group, data in groups.items():

            nums = [
                float(r[field])
                for r in data
                if r[field] is not None
            ]

            values[group] = (
                sum(nums) / len(nums)
                if nums
                else 0
            )

        difference = (
            values["TARGET"] - values["STOP"]
        )

        print(
            f"{label:<20}"
            f"{values['STOP']:>15.4f}"
            f"{values['TARGET']:>15.4f}"
            f"{values['TIME_EXIT']:>15.4f}"
            f"{difference:>15.4f}"
        )

    # ---------------------------------------------------------
    # Counts
    # ---------------------------------------------------------

    print()
    print("GROUP COUNTS")
    print("-" * 110)

    for group in groups:

        print(
            f"{group:<15}"
            f"{len(groups[group]):>10,}"
        )

    # ---------------------------------------------------------
    # High-score analysis
    # ---------------------------------------------------------

    print()
    print("SCORE >= 95")
    print("-" * 110)

    high_groups = defaultdict(list)

    for trade in result["trades"]:

        if trade["reason"] not in (
            "STOP",
            "TARGET1",
            "TARGET2",
        ):
            continue

        row = signal_map.get(
            (
                trade["market_id"],
                trade["entry_time"],
            )
        )

        if row is None:
            continue

        if row["score"] >= 95:

            group = (
                "STOP"
                if trade["reason"] == "STOP"
                else "TARGET"
            )

            high_groups[group].append(row)

    print(
        f"STOP  >=95 : "
        f"{len(high_groups['STOP']):,}"
    )

    print(
        f"TARGET>=95 : "
        f"{len(high_groups['TARGET']):,}"
    )

    for field, label in fields:

        stop_values = [
            float(r[field])
            for r in high_groups["STOP"]
            if r[field] is not None
        ]

        target_values = [
            float(r[field])
            for r in high_groups["TARGET"]
            if r[field] is not None
        ]

        if not stop_values or not target_values:
            continue

        stop_avg = sum(stop_values) / len(stop_values)
        target_avg = sum(target_values) / len(target_values)

        print(
            f"{label:<20}"
            f"STOP={stop_avg:>10.4f}  "
            f"TARGET={target_avg:>10.4f}  "
            f"Δ={target_avg-stop_avg:>10.4f}"
        )

    conn.close()


def main():

    analyze("1D")
    analyze("4h")


if __name__ == "__main__":
    main()
