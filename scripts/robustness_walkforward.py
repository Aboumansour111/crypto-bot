from __future__ import annotations

from collections import defaultdict
from scripts.analyze_filters_oos import (
    load_entry_data,
    load_next_bars,
    enrich,
    timestamp_year,
)
from scripts.compare_baseline_filtered import run_variant


MC_VALUES = (50, 55, 60)
ATR_VALUES = (0.050, 0.060, 0.070)


def period(ts):
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(
        int(ts),
        tz=timezone.utc,
    )

    return f"{dt.year}-H1" if dt.month <= 6 else f"{dt.year}-H2"


def stats(trades):
    n = len(trades)

    if not n:
        return {
            "n": 0,
            "stop": 0,
            "target": 0,
            "win": 0.0,
            "pf": 0.0,
            "pnl": 0.0,
        }

    stop = sum(
        1 for t in trades
        if t["reason"] == "STOP"
    )

    target = sum(
        1 for t in trades
        if t["reason"] in ("TARGET1", "TARGET2")
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

    return {
        "n": n,
        "stop": stop,
        "target": target,
        "win": wins / n * 100,
        "pf": gp / gl if gl else 999,
        "pnl": sum(float(t["pnl"]) for t in trades),
    }


def main():
    print("Loading data...")

    data = load_entry_data()
    next_bars = load_next_bars()

    result = run_variant(
        "1D",
        filtered=False,
    )

    trades = enrich(
        result["trades"],
        data,
        next_bars,
    )

    periods = defaultdict(list)

    for t in trades:
        periods[period(t["entry_time"])].append(t)

    print()
    print("=" * 120)
    print("ROBUSTNESS WALK-FORWARD GRID")
    print("=" * 120)

    for mc in MC_VALUES:
        for atr in ATR_VALUES:

            print()
            print(
                f"MC >= {mc}, ATR <= {atr:.3f}"
            )
            print("-" * 120)

            print(
                f"{'Period':<12}"
                f"{'N':>7}"
                f"{'STOP%':>9}"
                f"{'TARGET%':>10}"
                f"{'WIN%':>9}"
                f"{'PF':>9}"
                f"{'PnL':>20}"
            )

            total = []

            for p in sorted(periods):
                selected = [
                    t for t in periods[p]
                    if (
                        t["market_context"] >= mc
                        and t["atr_pct"] <= atr
                    )
                ]

                total.extend(selected)

                s = stats(selected)

                print(
                    f"{p:<12}"
                    f"{s['n']:>7}"
                    f"{s['stop']/s['n']*100 if s['n'] else 0:>8.1f}%"
                    f"{s['target']/s['n']*100 if s['n'] else 0:>9.1f}%"
                    f"{s['win']:>8.1f}%"
                    f"{s['pf']:>9.3f}"
                    f"{s['pnl']:>20,.2f}"
                )

            s = stats(total)

            print("-" * 120)
            print(
                f"{'TOTAL':<12}"
                f"{s['n']:>7}"
                f"{s['stop']/s['n']*100 if s['n'] else 0:>8.1f}%"
                f"{s['target']/s['n']*100 if s['n'] else 0:>9.1f}%"
                f"{s['win']:>8.1f}%"
                f"{s['pf']:>9.3f}"
                f"{s['pnl']:>20,.2f}"
            )


if __name__ == "__main__":
    main()
