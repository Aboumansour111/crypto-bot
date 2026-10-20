import sqlite3
from pathlib import Path
from collections import defaultdict
from itertools import product

from app.backtest.engine import run_backtest

DB = Path("/opt/crypto-bot/data/crypto.db")


def load_entry_data():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
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

    conn.close()

    return {
        (int(r["market_id"]), int(r["timestamp"])): dict(r)
        for r in rows
    }


def load_next_bar_map():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT market_id, timestamp
        FROM ohlcv
        WHERE timeframe = '1D'
        ORDER BY market_id, timestamp
    """).fetchall()

    conn.close()

    result = {}
    previous = {}

    for r in rows:
        market_id = int(r["market_id"])
        ts = int(r["timestamp"])

        if market_id in previous:
            result[(market_id, previous[market_id])] = ts

        previous[market_id] = ts

    return result


def enrich_trades(trades, entry_data, next_bar_map):
    enriched = []

    for trade in trades:
        market_id = int(trade["market_id"])
        entry_time = int(trade["entry_time"])

        signal_time = None

        # Entry is the next bar after signal.
        # Find the signal timestamp whose next bar is entry_time.
        for (mid, ts), next_ts in next_bar_map.items():
            if mid == market_id and next_ts == entry_time:
                signal_time = ts
                break

        if signal_time is None:
            continue

        data = entry_data.get((market_id, signal_time))

        if data is None:
            continue

        x = dict(trade)

        x["score"] = data["total_score"]
        x["trend"] = data["trend_score"]
        x["momentum"] = data["momentum_score"]
        x["volume"] = data["volume_score"]
        x["volatility"] = data["volatility_score"]
        x["market_context"] = data["market_context_score"]
        x["rsi"] = data["rsi_14"]
        x["atr_pct"] = data["atr_pct_14"]
        x["volume_ratio"] = data["volume_ratio_20"]

        enriched.append(x)

    return enriched


def stats(trades):
    if not trades:
        return None

    pnl = sum(float(t["pnl"]) for t in trades)

    wins = sum(
        1 for t in trades
        if float(t["pnl"]) > 0
    )

    gross_profit = sum(
        float(t["pnl"])
        for t in trades
        if float(t["pnl"]) > 0
    )

    gross_loss = abs(sum(
        float(t["pnl"])
        for t in trades
        if float(t["pnl"]) < 0
    ))

    pf = (
        gross_profit / gross_loss
        if gross_loss > 0
        else float("inf")
    )

    reasons = defaultdict(int)

    for t in trades:
        reasons[t["reason"]] += 1

    return {
        "n": len(trades),
        "win_rate": wins / len(trades) * 100,
        "pf": pf,
        "pnl": pnl,
        "stop": reasons["STOP"],
        "target": reasons["TARGET1"] + reasons["TARGET2"],
        "time": reasons["TIME_EXIT"],
    }


def print_table(title, results):
    print("\n" + "=" * 120)
    print(title)
    print("=" * 120)

    print(
        f"{'FILTER':<48}"
        f"{'TRADES':>8}"
        f"{'STOP%':>9}"
        f"{'TARGET%':>10}"
        f"{'TIME%':>9}"
        f"{'WIN%':>9}"
        f"{'PF':>9}"
        f"{'PNL':>17}"
    )

    print("-" * 120)

    for name, s in results:
        if s is None:
            continue

        print(
            f"{name:<48}"
            f"{s['n']:>8}"
            f"{s['stop']/s['n']*100:>8.1f}%"
            f"{s['target']/s['n']*100:>9.1f}%"
            f"{s['time']/s['n']*100:>8.1f}%"
            f"{s['win_rate']:>8.1f}%"
            f"{s['pf']:>9.3f}"
            f"{s['pnl']:>17,.0f}"
        )


# ============================================================
# LOAD
# ============================================================

print("=" * 120)
print("1D FILTER GRID ANALYSIS")
print("=" * 120)

print("\nLoading entry features...")
entry_data = load_entry_data()
print(f"Entry feature rows: {len(entry_data):,}")

print("Loading OHLCV next-bar mapping...")
next_bar_map = load_next_bar_map()
print(f"Next-bar mappings: {len(next_bar_map):,}")

print("\nRunning corrected 1D backtest...")
result = run_backtest("1D")
raw_trades = result["trades"]

print(f"Backtest trades: {len(raw_trades):,}")

trades = enrich_trades(
    raw_trades,
    entry_data,
    next_bar_map
)

print(f"Matched trades: {len(trades):,}")

if not trades:
    raise SystemExit(
        "ERROR: No trades matched to entry features."
    )


# ============================================================
# BASELINE
# ============================================================

base = stats(trades)

print("\n" + "=" * 80)
print("BASELINE")
print("=" * 80)

print(f"Trades        : {base['n']}")
print(f"STOP          : {base['stop']}")
print(f"TARGET        : {base['target']}")
print(f"TIME_EXIT     : {base['time']}")
print(f"Win Rate      : {base['win_rate']:.2f}%")
print(f"Profit Factor : {base['pf']:.3f}")
print(f"PnL           : {base['pnl']:,.2f}")


# ============================================================
# 1 — MARKET CONTEXT
# ============================================================

results = []

for x in [45, 50, 55, 60, 65, 70, 75, 80]:
    subset = [
        t for t in trades
        if t["market_context"] >= x
    ]

    results.append(
        (f"MarketContext >= {x}", stats(subset))
    )

print_table(
    "SINGLE FILTER — MARKET CONTEXT",
    results
)


# ============================================================
# 2 — VOLATILITY
# ============================================================

results = []

for x in [55, 60, 65, 70, 75, 80, 85, 90]:
    subset = [
        t for t in trades
        if t["volatility"] >= x
    ]

    results.append(
        (f"Volatility >= {x}", stats(subset))
    )

print_table(
    "SINGLE FILTER — VOLATILITY",
    results
)


# ============================================================
# 3 — ATR%
# ============================================================

results = []

for x in [
    0.040,
    0.045,
    0.050,
    0.055,
    0.060,
    0.065,
    0.070,
    0.075,
]:
    subset = [
        t for t in trades
        if t["atr_pct"] <= x
    ]

    results.append(
        (f"ATR% <= {x:.3f}", stats(subset))
    )

print_table(
    "SINGLE FILTER — ATR%",
    results
)


# ============================================================
# 4 — VOLUME RATIO
# ============================================================

results = []

for x in [
    1.2,
    1.4,
    1.6,
    1.8,
    2.0,
    2.2,
    2.5,
    3.0,
]:
    subset = [
        t for t in trades
        if t["volume_ratio"] <= x
    ]

    results.append(
        (f"VolumeRatio <= {x:.1f}", stats(subset))
    )

print_table(
    "SINGLE FILTER — VOLUME RATIO",
    results
)


# ============================================================
# 5 — MARKET CONTEXT + ATR%
# ============================================================

results = []

for mc, atr in product(
    [50, 55, 60, 65, 70],
    [0.045, 0.050, 0.055, 0.060, 0.065],
):
    subset = [
        t for t in trades
        if t["market_context"] >= mc
        and t["atr_pct"] <= atr
    ]

    if len(subset) >= 20:
        results.append((
            f"MC>={mc} + ATR%<={atr:.3f}",
            stats(subset)
        ))

results.sort(
    key=lambda x: (
        x[1]["pf"],
        x[1]["pnl"]
    ),
    reverse=True
)

print_table(
    "TOP 20 — MARKET CONTEXT + ATR%",
    results[:20]
)


# ============================================================
# 6 — MARKET CONTEXT + VOLATILITY
# ============================================================

results = []

for mc, vol in product(
    [50, 55, 60, 65, 70],
    [60, 65, 70, 75, 80, 85],
):
    subset = [
        t for t in trades
        if t["market_context"] >= mc
        and t["volatility"] >= vol
    ]

    if len(subset) >= 20:
        results.append((
            f"MC>={mc} + Vol>={vol}",
            stats(subset)
        ))

results.sort(
    key=lambda x: (
        x[1]["pf"],
        x[1]["pnl"]
    ),
    reverse=True
)

print_table(
    "TOP 20 — MARKET CONTEXT + VOLATILITY",
    results[:20]
)


# ============================================================
# 7 — MARKET CONTEXT + ATR% + VOLUME RATIO
# ============================================================

results = []

for mc, atr, vr in product(
    [50, 55, 60, 65],
    [0.050, 0.055, 0.060, 0.065],
    [1.6, 1.8, 2.0, 2.2],
):
    subset = [
        t for t in trades
        if t["market_context"] >= mc
        and t["atr_pct"] <= atr
        and t["volume_ratio"] <= vr
    ]

    if len(subset) >= 20:
        results.append((
            f"MC>={mc} + ATR%<={atr:.3f} + VR<={vr:.1f}",
            stats(subset)
        ))

results.sort(
    key=lambda x: (
        x[1]["pf"],
        x[1]["pnl"]
    ),
    reverse=True
)

print_table(
    "TOP 20 — MARKET CONTEXT + ATR% + VOLUME RATIO",
    results[:20]
)


print("\n" + "=" * 120)
print("GRID ANALYSIS COMPLETE")
print("=" * 120)
