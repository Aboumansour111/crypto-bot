import sqlite3
from pathlib import Path
from collections import defaultdict

from app.backtest.engine import run_backtest

DB = Path("/opt/crypto-bot/data/crypto.db")

# Candidate filters discovered by the previous grid.
FILTERS = [
    ("BASELINE", None),

    ("MC>=55 + ATR<=0.060",
     lambda t: t["market_context"] >= 55
               and t["atr_pct"] <= 0.060),

    ("MC>=55 + ATR<=0.060 + VR<=1.8",
     lambda t: t["market_context"] >= 55
               and t["atr_pct"] <= 0.060
               and t["volume_ratio"] <= 1.8),

    ("MC>=55 + ATR<=0.060 + VR<=2.0",
     lambda t: t["market_context"] >= 55
               and t["atr_pct"] <= 0.060
               and t["volume_ratio"] <= 2.0),

    ("MC>=55 + ATR<=0.060 + VR<=2.2",
     lambda t: t["market_context"] >= 55
               and t["atr_pct"] <= 0.060
               and t["volume_ratio"] <= 2.2),
]


def load_entry_data():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT
            s.market_id,
            s.timestamp,
            s.total_score,
            s.trend_score,
            s.momentum_score,
            s.volume_score,
            s.volatility_score,
            s.market_context_score,
            f.rsi_14,
            f.atr_pct_14,
            f.volume_ratio_20
        FROM strategy_scores s
        JOIN features f
          ON f.market_id = s.market_id
         AND f.timeframe = s.timeframe
         AND f.timestamp = s.timestamp
        WHERE s.timeframe = '1D'
    """).fetchall()

    con.close()

    return {
        (int(r["market_id"]), int(r["timestamp"])): dict(r)
        for r in rows
    }


def load_next_bars():
    con = sqlite3.connect(DB)
    rows = con.execute("""
        SELECT market_id, timestamp
        FROM ohlcv
        WHERE timeframe='1D'
        ORDER BY market_id, timestamp
    """).fetchall()
    con.close()

    result = {}
    previous = {}

    for market_id, timestamp in rows:
        market_id = int(market_id)
        timestamp = int(timestamp)

        if market_id in previous:
            result[(market_id, previous[market_id])] = timestamp

        previous[market_id] = timestamp

    return result


def enrich(trades, data, next_bars):
    out = []

    # Build reverse lookup once.
    reverse = {
        (mid, next_ts): signal_ts
        for (mid, signal_ts), next_ts in next_bars.items()
    }

    for trade in trades:
        market_id = int(trade["market_id"])
        entry_time = int(trade["entry_time"])

        signal_time = reverse.get(
            (market_id, entry_time)
        )

        if signal_time is None:
            continue

        f = data.get(
            (market_id, signal_time)
        )

        if f is None:
            continue

        x = dict(trade)

        x["score"] = f["total_score"]
        x["trend"] = f["trend_score"]
        x["momentum"] = f["momentum_score"]
        x["volume"] = f["volume_score"]
        x["volatility"] = f["volatility_score"]
        x["market_context"] = f["market_context_score"]
        x["rsi"] = f["rsi_14"]
        x["atr_pct"] = f["atr_pct_14"]
        x["volume_ratio"] = f["volume_ratio_20"]

        out.append(x)

    return out


def timestamp_year(ts):
    return int(
        __import__("datetime").datetime
        .fromtimestamp(ts)
        .year
    )


def stats(trades):
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
        if t["reason"] == "STOP"
    )

    target = sum(
        1 for t in trades
        if t["reason"] in ("TARGET1", "TARGET2")
    )

    time_exit = sum(
        1 for t in trades
        if t["reason"] == "TIME_EXIT"
    )

    wins = sum(
        1 for t in trades
        if float(t["pnl"]) > 0
    )

    gp = sum(
        float(t["pnl"])
        for t in trades
        if float(t["pnl"]) > 0
    )

    gl = abs(sum(
        float(t["pnl"])
        for t in trades
        if float(t["pnl"]) < 0
    ))

    pnl = sum(float(t["pnl"]) for t in trades)

    return {
        "n": len(trades),
        "stop": stop,
        "target": target,
        "time": time_exit,
        "win": wins / len(trades) * 100,
        "pf": gp / gl if gl else 999,
        "pnl": pnl,
    }


print("=" * 120)
print("1D OUT-OF-SAMPLE FILTER TEST")
print("=" * 120)

data = load_entry_data()
next_bars = load_next_bars()

print(f"Entry data : {len(data):,}")
print(f"Next bars  : {len(next_bars):,}")

print("\nRunning corrected 1D backtest...")
result = run_backtest("1D")
trades = enrich(result["trades"], data, next_bars)

print(f"Matched trades: {len(trades):,}")

# ------------------------------------------------------------
# TRAIN / TEST
#
# Train: before 2026
# Test : 2026
# ------------------------------------------------------------

train = [
    t for t in trades
    if timestamp_year(int(t["entry_time"])) < 2026
]

test = [
    t for t in trades
    if timestamp_year(int(t["entry_time"])) >= 2026
]


def print_block(label, rows):
    print("\n" + "=" * 120)
    print(label)
    print("=" * 120)

    print(
        f"{'FILTER':<44}"
        f"{'N':>7}"
        f"{'STOP%':>9}"
        f"{'TARGET%':>10}"
        f"{'WIN%':>9}"
        f"{'PF':>9}"
        f"{'PNL':>17}"
    )

    print("-" * 120)

    for name, subset in rows:
        s = stats(subset)

        print(
            f"{name:<44}"
            f"{s['n']:>7}"
            f"{s['stop']/s['n']*100 if s['n'] else 0:>8.1f}%"
            f"{s['target']/s['n']*100 if s['n'] else 0:>9.1f}%"
            f"{s['win']:>8.1f}%"
            f"{s['pf']:>9.3f}"
            f"{s['pnl']:>17,.0f}"
        )


for period_name, period in [
    ("TRAIN — 2024-2025", train),
    ("TEST — 2026", test),
]:
    rows = []

    for name, condition in FILTERS:
        if condition is None:
            subset = period
        else:
            subset = [
                t for t in period
                if condition(t)
            ]

        rows.append((name, subset))

    print_block(period_name, rows)


print("\n" + "=" * 120)
print("OUT-OF-SAMPLE TEST COMPLETE")
print("=" * 120)
