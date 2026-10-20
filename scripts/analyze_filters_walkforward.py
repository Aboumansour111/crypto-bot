import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from app.backtest.engine import run_backtest


DB = Path("/opt/crypto-bot/data/crypto.db")

FILTERS = [
    ("BASELINE", None),
    (
        "MC>=55 + ATR<=0.060",
        lambda t: (
            t["market_context"] >= 55
            and t["atr_pct"] <= 0.060
        ),
    ),
]

WINDOWS = [
    ("2024-H1", "2024-01-01", "2024-06-30"),
    ("2024-H2", "2024-07-01", "2024-12-31"),
    ("2025-H1", "2025-01-01", "2025-06-30"),
    ("2025-H2", "2025-07-01", "2025-12-31"),
    ("2026-H1", "2026-01-01", "2026-06-30"),
    ("2026-H2", "2026-07-01", "2026-12-31"),
]


def ts_to_date(ts):
    return datetime.fromtimestamp(
        int(ts), timezone.utc
    ).strftime("%Y-%m-%d")


def load_entry_data():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            ss.market_id,
            ss.timestamp AS signal_timestamp,
            ss.total_score,
            ss.market_context_score AS market_context,
            f.atr_pct_14 AS atr_pct,
            f.volume_ratio_20 AS volume_ratio
        FROM strategy_scores ss
        JOIN features f
          ON f.market_id = ss.market_id
         AND f.timeframe = ss.timeframe
         AND f.timestamp = ss.timestamp
        WHERE ss.timeframe = '1D'
          AND ss.candidate = 1
        ORDER BY ss.timestamp, ss.market_id
        """
    ).fetchall()

    ohlcv = conn.execute(
        """
        SELECT market_id, timestamp, open
        FROM ohlcv
        WHERE timeframe = '1D'
        ORDER BY market_id, timestamp
        """
    ).fetchall()

    conn.close()

    grouped = {}

    for r in ohlcv:
        grouped.setdefault(r["market_id"], []).append(r)

    next_bar = {}

    for market_id, bars in grouped.items():
        for i in range(len(bars) - 1):
            next_bar[
                (market_id, bars[i]["timestamp"])
            ] = bars[i + 1]["timestamp"]

    entries = []

    for r in rows:
        key = (
            r["market_id"],
            r["signal_timestamp"],
        )

        if key not in next_bar:
            continue

        entries.append(
            {
                "market_id": r["market_id"],
                "signal_timestamp": r["signal_timestamp"],
                "entry_timestamp": next_bar[key],
                "total_score": float(r["total_score"]),
                "market_context": float(r["market_context"]),
                "atr_pct": float(r["atr_pct"]),
                "volume_ratio": float(r["volume_ratio"]),
            }
        )

    return entries


def summarize(trades):
    if not trades:
        return {
            "n": 0,
            "stop": 0,
            "target": 0,
            "time": 0,
            "win": 0,
            "pf": 0,
            "pnl": 0,
        }

    stop = sum(
        1 for t in trades
        if t.get("reason") == "STOP"
    )

    target = sum(
        1 for t in trades
        if t.get("reason") in ("TARGET1", "TARGET2")
    )

    time_exit = sum(
        1 for t in trades
        if t.get("reason") == "TIME_EXIT"
    )

    wins = sum(
        1 for t in trades
        if float(t.get("pnl", 0) or 0) > 0
    )

    gross_profit = sum(
        float(t.get("pnl", 0) or 0)
        for t in trades
        if float(t.get("pnl", 0) or 0) > 0
    )

    gross_loss = abs(
        sum(
            float(t.get("pnl", 0) or 0)
            for t in trades
            if float(t.get("pnl", 0) or 0) < 0
        )
    )

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0
    )

    return {
        "n": len(trades),
        "stop": stop,
        "target": target,
        "time": time_exit,
        "win": wins,
        "pf": pf,
        "pnl": sum(
            float(t.get("pnl", 0) or 0)
            for t in trades
        ),
    }


def run_period(all_trades, entries, start, end, filter_fn):
    selected_keys = set()

    for e in entries:
        date = ts_to_date(e["entry_timestamp"])

        if start <= date <= end:
            if filter_fn is None or filter_fn(e):
                selected_keys.add(
                    (
                        e["market_id"],
                        e["entry_timestamp"],
                    )
                )

    period_trades = []

    for t in all_trades:
        market_id = t.get("market_id")
        entry_time = t.get("entry_time")

        if entry_time is None:
            continue

        key = (
            market_id,
            entry_time,
        )

        if key in selected_keys:
            period_trades.append(t)

    return summarize(period_trades)


def main():
    print("=" * 120)
    print("1D WALK-FORWARD FILTER TEST")
    print("=" * 120)

    entries = load_entry_data()

    print(f"Entry data : {len(entries):,}")

    print("\nRunning corrected 1D backtest...")

    result = run_backtest("1D")
    all_trades = result["trades"]

    print(f"Backtest trades: {len(all_trades):,}")

    print("\n" + "=" * 120)
    print("WALK-FORWARD RESULTS")
    print("=" * 120)

    print(
        f"{'PERIOD':<12}"
        f"{'FILTER':<38}"
        f"{'N':>6}"
        f"{'STOP%':>9}"
        f"{'TARGET%':>10}"
        f"{'WIN%':>9}"
        f"{'PF':>9}"
        f"{'PNL':>16}"
    )

    print("-" * 120)

    for period, start, end in WINDOWS:
        for filter_name, filter_fn in FILTERS:

            s = run_period(
                all_trades,
                entries,
                start,
                end,
                filter_fn,
            )

            n = s["n"]

            stop_pct = (
                s["stop"] / n * 100
                if n else 0
            )

            target_pct = (
                s["target"] / n * 100
                if n else 0
            )

            win_pct = (
                s["win"] / n * 100
                if n else 0
            )

            print(
                f"{period:<12}"
                f"{filter_name:<38}"
                f"{n:>6}"
                f"{stop_pct:>8.1f}%"
                f"{target_pct:>9.1f}%"
                f"{win_pct:>8.1f}%"
                f"{s['pf']:>9.3f}"
                f"{s['pnl']:>16,.0f}"
            )


if __name__ == "__main__":
    main()
