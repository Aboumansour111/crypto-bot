from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"


def calc(trades, cap=None):
    pnls = []

    for t in trades:
        pnl = float(t["pnl"])

        if cap is not None:
            if pnl > cap:
                pnl = cap
            elif pnl < -cap:
                pnl = -cap

        pnls.append(pnl)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gp = sum(wins)
    gl = abs(sum(losses))

    return {
        "trades": len(pnls),
        "pnl": sum(pnls),
        "win": (
            len(wins) / len(pnls) * 100
            if pnls else 0
        ),
        "pf": (
            gp / gl
            if gl > 0
            else None
        ),
    }


def yearly(trades, cap):
    data = defaultdict(list)

    for t in trades:
        y = datetime.fromtimestamp(
            t["entry_time"],
            tz=timezone.utc,
        ).year

        pnl = float(t["pnl"])

        if cap is not None:
            pnl = min(max(pnl, -cap), cap)

        data[y].append(pnl)

    result = {}

    for y, pnls in sorted(data.items()):
        wins = sum(1 for p in pnls if p > 0)
        losses = [p for p in pnls if p < 0]
        profits = [p for p in pnls if p > 0]

        gp = sum(profits)
        gl = abs(sum(losses))

        result[y] = (
            len(pnls),
            sum(pnls),
            wins / len(pnls) * 100 if pnls else 0,
            gp / gl if gl else None,
        )

    return result


def main():
    print("Running FILTERED backtest...")

    result = run_variant(
        TIMEFRAME,
        filtered=True,
    )

    trades = result["trades"]

    caps = [
        None,
        500_000,
        250_000,
        100_000,
    ]

    print("\n" + "=" * 90)
    print("OUTLIER / PNL CAP TEST")
    print("=" * 90)

    print(
        f"{'Scenario':<20}"
        f"{'Trades':>10}"
        f"{'PnL':>20}"
        f"{'Win%':>12}"
        f"{'PF':>10}"
    )

    print("-" * 75)

    for cap in caps:
        m = calc(trades, cap)

        label = (
            "NO CAP"
            if cap is None
            else f"CAP {cap:,.0f}"
        )

        pf = (
            f"{m['pf']:.3f}"
            if m["pf"] is not None
            else "-"
        )

        print(
            f"{label:<20}"
            f"{m['trades']:>10}"
            f"{m['pnl']:>20,.2f}"
            f"{m['win']:>11.2f}%"
            f"{pf:>10}"
        )

    print("\n" + "=" * 90)
    print("YEARLY OUTLIER TEST")
    print("=" * 90)

    print(
        f"{'Year':<8}"
        f"{'No Cap PnL':>20}"
        f"{'500K Cap':>20}"
        f"{'250K Cap':>20}"
        f"{'100K Cap':>20}"
    )

    print("-" * 90)

    yearly_data = {
        cap: yearly(trades, cap)
        for cap in caps
    }

    years = sorted(
        set(
            y
            for data in yearly_data.values()
            for y in data
        )
    )

    for y in years:
        values = []

        for cap in caps:
            values.append(
                yearly_data[cap].get(
                    y,
                    (0, 0, 0, None)
                )[1]
            )

        print(
            f"{y:<8}"
            f"{values[0]:>20,.2f}"
            f"{values[1]:>20,.2f}"
            f"{values[2]:>20,.2f}"
            f"{values[3]:>20,.2f}"
        )


if __name__ == "__main__":
    main()
