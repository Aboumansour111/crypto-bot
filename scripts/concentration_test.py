from __future__ import annotations

from collections import defaultdict
from app.config.settings import settings
from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"


def metrics(trades):
    pnls = [float(t["pnl"]) for t in trades]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "trades": len(pnls),
        "pnl": sum(pnls),
        "win_rate": (
            len(wins) / len(pnls) * 100
            if pnls else 0
        ),
        "pf": (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        ),
    }


def filter_symbols(trades, excluded):
    return [
        t for t in trades
        if t["symbol"] not in excluded
    ]


def print_result(label, trades):
    m = metrics(trades)

    pf = (
        f"{m['pf']:.3f}"
        if m["pf"] is not None
        else "-"
    )

    print(
        f"{label:<25}"
        f"{m['trades']:>8}"
        f"{m['pnl']:>18,.2f}"
        f"{m['win_rate']:>11.2f}%"
        f"{pf:>10}"
    )


def main():
    print("Running FILTERED backtest...")
    result = run_variant(
        TIMEFRAME,
        filtered=True,
    )

    trades = result["trades"]

    by_symbol = defaultdict(float)

    for t in trades:
        by_symbol[t["symbol"]] += float(t["pnl"])

    ranked = sorted(
        by_symbol.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    top5 = {
        symbol
        for symbol, _ in ranked[:5]
    }

    top10 = {
        symbol
        for symbol, _ in ranked[:10]
    }

    top1 = {
        ranked[0][0]
    } if ranked else set()

    top2 = {
        symbol
        for symbol, _ in ranked[:2]
    }

    print("\n" + "=" * 85)
    print("CONCENTRATION / LEAVE-ONE-OUT TEST")
    print("=" * 85)

    print(
        f"{'Scenario':<25}"
        f"{'Trades':>8}"
        f"{'PnL':>18}"
        f"{'Win Rate':>11}"
        f"{'PF':>10}"
    )

    print("-" * 75)

    print_result(
        "ALL FILTERED",
        trades,
    )

    print_result(
        "WITHOUT TOP 1",
        filter_symbols(trades, top1),
    )

    print_result(
        "WITHOUT TOP 2",
        filter_symbols(trades, top2),
    )

    print_result(
        "WITHOUT TOP 5",
        filter_symbols(trades, top5),
    )

    print_result(
        "WITHOUT TOP 10",
        filter_symbols(trades, top10),
    )

    print("\n" + "=" * 85)
    print("TOP SYMBOLS")
    print("=" * 85)

    for i, (symbol, pnl) in enumerate(ranked[:20], 1):
        print(
            f"{i:>2}. "
            f"{symbol:<20}"
            f"{pnl:>18,.2f}"
        )

    print("\n" + "=" * 85)
    print("YEARLY PNL WITHOUT TOP 5")
    print("=" * 85)

    remaining = filter_symbols(
        trades,
        top5,
    )

    yearly = defaultdict(float)

    from datetime import datetime, timezone

    for t in remaining:
        year = datetime.fromtimestamp(
            t["entry_time"],
            tz=timezone.utc,
        ).year

        yearly[year] += float(t["pnl"])

    for year in sorted(yearly):
        print(
            f"{year}: "
            f"{yearly[year]:,.2f}"
        )


if __name__ == "__main__":
    main()
