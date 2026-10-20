from __future__ import annotations

from scripts.analyze_filters_oos import (
    load_entry_data,
    load_next_bars,
    enrich,
    timestamp_year,
    stats,
)

MC_VALUES = (50, 55, 60)
ATR_VALUES = (0.050, 0.060, 0.070)


def pct(value, total):
    return value / total * 100 if total else 0.0


def main():
    print("Loading data...")

    data = load_entry_data()
    next_bars = load_next_bars()

    from scripts.compare_baseline_filtered import run_variant

    result = run_variant(
        "1D",
        filtered=False,
    )

    trades = enrich(
        result["trades"],
        data,
        next_bars,
    )

    train = [
        t for t in trades
        if timestamp_year(int(t["entry_time"])) < 2026
    ]

    test = [
        t for t in trades
        if timestamp_year(int(t["entry_time"])) >= 2026
    ]

    print()
    print("=" * 120)
    print("OOS ROBUSTNESS GRID")
    print("=" * 120)

    print(
        f"{'MC':>6}"
        f"{'ATR':>8}"
        f"{'PERIOD':<12}"
        f"{'N':>8}"
        f"{'STOP%':>10}"
        f"{'TARGET%':>11}"
        f"{'WIN%':>10}"
        f"{'PF':>9}"
        f"{'PNL':>20}"
    )

    print("-" * 120)

    for mc in MC_VALUES:
        for atr in ATR_VALUES:

            def filt(t):
                return (
                    t["market_context"] >= mc
                    and t["atr_pct"] <= atr
                )

            train_f = [t for t in train if filt(t)]
            test_f = [t for t in test if filt(t)]

            tr = stats(train_f)
            te = stats(test_f)

            for period, s in (
                ("TRAIN", tr),
                ("TEST", te),
            ):
                n = s["n"]

                stop_pct = pct(s["stop"], n)
                target_pct = pct(s["target"], n)
                win_pct = pct(s["win"], n)

                pf = (
                    f"{s['pf']:.3f}"
                    if s["pf"] is not None
                    else "-"
                )

                print(
                    f"{mc:>6}"
                    f"{atr * 100:>7.1f}%"
                    f"{period:<12}"
                    f"{n:>8}"
                    f"{stop_pct:>9.1f}%"
                    f"{target_pct:>10.1f}%"
                    f"{win_pct:>9.1f}%"
                    f"{pf:>9}"
                    f"{s['pnl']:>20,.2f}"
                )

            print("-" * 120)


if __name__ == "__main__":
    main()
