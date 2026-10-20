from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from app.config.settings import settings
from scripts.compare_baseline_filtered import run_variant

DB_PATH = settings.db_path
TIMEFRAME = "1D"


def year_from_ts(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).year


def calculate_yearly(trades):
    by_year = defaultdict(list)

    for trade in trades:
        year = year_from_ts(trade["entry_time"])
        by_year[year].append(trade)

    result = {}

    for year, rows in sorted(by_year.items()):
        pnls = [float(t["pnl"]) for t in rows]

        wins = sum(1 for p in pnls if p > 0)
        losses = [p for p in pnls if p < 0]
        profits = [p for p in pnls if p > 0]

        gross_profit = sum(profits)
        gross_loss = abs(sum(losses))

        pf = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        result[year] = {
            "trades": len(rows),
            "pnl": sum(pnls),
            "win_rate": (
                wins / len(rows) * 100
                if rows else 0
            ),
            "pf": pf,
        }

    return result


def symbol_concentration(trades):
    by_symbol = defaultdict(lambda: {
        "trades": 0,
        "pnl": 0.0,
    })

    for trade in trades:
        symbol = trade["symbol"]
        by_symbol[symbol]["trades"] += 1
        by_symbol[symbol]["pnl"] += float(trade["pnl"])

    ranked = sorted(
        by_symbol.items(),
        key=lambda x: x[1]["pnl"],
        reverse=True,
    )

    total_pnl = sum(
        data["pnl"]
        for data in by_symbol.values()
    )

    return ranked, total_pnl


def print_global(baseline, filtered):
    print("\n" + "=" * 78)
    print("GLOBAL BASELINE vs FILTERED")
    print("=" * 78)

    print(
        f"{'Metric':<25}"
        f"{'Baseline':>20}"
        f"{'Filtered':>20}"
    )

    print("-" * 68)

    metrics = [
        ("Final Equity", "final_equity"),
        ("Return %", "return_pct"),
        ("Max Drawdown %", "max_drawdown_pct"),
        ("Trades", "trade_count"),
        ("Win Rate %", "win_rate"),
        ("Profit Factor", "profit_factor"),
        ("Average Trade", "average_trade"),
        ("Gross Profit", "gross_profit"),
        ("Gross Loss", "gross_loss"),
        ("Fees", "total_fees"),
        ("Turnover", "total_turnover"),
        ("Slippage", "total_slippage"),
    ]

    for label, key in metrics:
        a = baseline.get(key)
        b = filtered.get(key)

        if a is None:
            a = 0

        if b is None:
            b = 0

        print(
            f"{label:<25}"
            f"{a:>20,.4f}"
            f"{b:>20,.4f}"
        )


def print_yearly(baseline, filtered):
    base = calculate_yearly(
        baseline["trades"]
    )

    filt = calculate_yearly(
        filtered["trades"]
    )

    years = sorted(
        set(base) | set(filt)
    )

    print("\n" + "=" * 78)
    print("YEAR-BY-YEAR")
    print("=" * 78)

    print(
        f"{'Year':<7}"
        f"{'Base N':>8}"
        f"{'Base PnL':>18}"
        f"{'Base Win%':>11}"
        f"{'Base PF':>9}"
        f"{'Filt N':>8}"
        f"{'Filt PnL':>18}"
        f"{'Filt Win%':>11}"
        f"{'Filt PF':>9}"
    )

    print("-" * 105)

    for year in years:
        b = base.get(
            year,
            {
                "trades": 0,
                "pnl": 0,
                "win_rate": 0,
                "pf": None,
            },
        )

        f = filt.get(
            year,
            {
                "trades": 0,
                "pnl": 0,
                "win_rate": 0,
                "pf": None,
            },
        )

        bpf = (
            f"{b['pf']:.3f}"
            if b["pf"] is not None
            else "-"
        )

        fpf = (
            f"{f['pf']:.3f}"
            if f["pf"] is not None
            else "-"
        )

        print(
            f"{year:<7}"
            f"{b['trades']:>8}"
            f"{b['pnl']:>18,.2f}"
            f"{b['win_rate']:>10.2f}%"
            f"{bpf:>9}"
            f"{f['trades']:>8}"
            f"{f['pnl']:>18,.2f}"
            f"{f['win_rate']:>10.2f}%"
            f"{fpf:>9}"
        )


def print_concentration(filtered):
    ranked, total_pnl = symbol_concentration(
        filtered["trades"]
    )

    print("\n" + "=" * 78)
    print("FILTERED SYMBOL CONCENTRATION")
    print("=" * 78)

    print(f"Unique symbols: {len(ranked)}")
    print(f"Total trade PnL: {total_pnl:,.2f}")

    for n in (5, 10, 20):
        top_pnl = sum(
            data["pnl"]
            for _, data in ranked[:n]
        )

        share = (
            top_pnl / total_pnl * 100
            if total_pnl
            else 0
        )

        print(
            f"Top {n:<2} PnL: "
            f"{top_pnl:>18,.2f} "
            f"({share:>6.2f}% of total)"
        )

    positive = sum(
        1
        for _, data in ranked
        if data["pnl"] > 0
    )

    negative = sum(
        1
        for _, data in ranked
        if data["pnl"] < 0
    )

    zero = sum(
        1
        for _, data in ranked
        if data["pnl"] == 0
    )

    print()
    print(f"Positive symbols: {positive}")
    print(f"Negative symbols: {negative}")
    print(f"Zero PnL symbols: {zero}")

    print("\nTop 20 symbols:")
    print(
        f"{'Symbol':<22}"
        f"{'Trades':>8}"
        f"{'PnL':>20}"
    )

    print("-" * 52)

    for symbol, data in ranked[:20]:
        print(
            f"{symbol:<22}"
            f"{data['trades']:>8}"
            f"{data['pnl']:>20,.2f}"
        )


def main():
    print("Running BASELINE...")
    baseline = run_variant(
        TIMEFRAME,
        filtered=False,
    )

    print("Running FILTERED...")
    filtered = run_variant(
        TIMEFRAME,
        filtered=True,
    )

    print_global(
        baseline,
        filtered,
    )

    print_yearly(
        baseline,
        filtered,
    )

    print_concentration(
        filtered,
    )


if __name__ == "__main__":
    main()
