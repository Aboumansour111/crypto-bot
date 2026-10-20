from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"


def year(ts):
    return datetime.fromtimestamp(
        ts,
        tz=timezone.utc,
    ).year


def main():
    print("Running FILTERED backtest...")

    result = run_variant(
        TIMEFRAME,
        filtered=True,
    )

    trades = result["trades"]

    symbols = defaultdict(list)

    for trade in trades:
        symbols[trade["symbol"]].append(trade)

    totals = []

    for symbol, rows in symbols.items():
        pnl = sum(
            float(t["pnl"])
            for t in rows
        )

        totals.append(
            (symbol, pnl, rows)
        )

    totals.sort(
        key=lambda x: x[1],
        reverse=True,
    )

    print("\n" + "=" * 100)
    print("TOP 15 SYMBOLS — YEARLY PERFORMANCE")
    print("=" * 100)

    for rank, (symbol, total_pnl, rows) in enumerate(
        totals[:15],
        1,
    ):
        yearly = defaultdict(list)

        for trade in rows:
            yearly[year(trade["entry_time"])].append(
                trade
            )

        print(
            f"\n#{rank} {symbol}"
            f" | Total PnL: {total_pnl:,.2f}"
            f" | Trades: {len(rows)}"
        )

        print(
            f"{'Year':<8}"
            f"{'Trades':>10}"
            f"{'PnL':>20}"
            f"{'Win%':>12}"
        )

        print("-" * 55)

        for y in sorted(yearly):
            yr_trades = yearly[y]

            pnls = [
                float(t["pnl"])
                for t in yr_trades
            ]

            wins = sum(
                1 for p in pnls
                if p > 0
            )

            yr_pnl = sum(pnls)

            win_rate = (
                wins / len(pnls) * 100
                if pnls else 0
            )

            print(
                f"{y:<8}"
                f"{len(yr_trades):>10}"
                f"{yr_pnl:>20,.2f}"
                f"{win_rate:>11.2f}%"
            )


if __name__ == "__main__":
    main()
