from datetime import datetime, timezone

from scripts.compare_baseline_filtered import (
    run_variant,
    INITIAL_CAPITAL,
)


TEST_START = int(
    datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
)


def year(ts):
    return datetime.fromtimestamp(
        int(ts), tz=timezone.utc
    ).year


def metrics(trades):
    pnls = [float(t["pnl"]) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    return {
        "n": len(trades),
        "pnl": sum(pnls),
        "win": len(wins) / len(pnls) * 100 if pnls else 0,
        "pf": gross_profit / gross_loss if gross_loss else None,
        "avg": sum(pnls) / len(pnls) if pnls else 0,
    }


def report(label, trades):
    m = metrics(trades)
    pf = f"{m['pf']:.3f}" if m["pf"] is not None else "N/A"

    print(f"\n{label}")
    print(f"Trades       : {m['n']}")
    print(f"Net PnL      : {m['pnl']:,.2f}")
    print(f"Win rate     : {m['win']:.2f}%")
    print(f"Profit factor: {pf}")
    print(f"Average trade: {m['avg']:,.2f}")


def main():
    print("Running baseline and fixed-filter backtests...")
    baseline = run_variant("1D", filtered=False)
    filtered = run_variant("1D", filtered=True)

    for label, result in (
        ("BASELINE", baseline),
        ("FILTERED MC>=55 AND ATR<=6%", filtered),
    ):
        trades = result["trades"]

        train_candidates = [
            t for t in trades
            if year(t["entry_time"]) < 2026
        ]
        train = [
            t for t in train_candidates
            if int(t["exit_time"]) < TEST_START
        ]
        train_crossing = len(train_candidates) - len(train)

        test = [
            t for t in trades
            if year(t["entry_time"]) == 2026
        ]

        print("\n" + "=" * 68)
        print(label)
        print("=" * 68)
        print(f"Training trades excluded for crossing into 2026: {train_crossing}")
        report("TRAIN: entries in 2024-2025, closed before 2026", train)
        report("TEST: entries in 2026 (partial year)", test)

        # Year-level diagnostic for 2026 entries.
        for y in (2024, 2025, 2026):
            rows = [t for t in trades if year(t["entry_time"]) == y]
            report(f"Entry year {y} (raw cohort)", rows)

    print("\nNotes:")
    print("- The 2026 test year is incomplete.")
    print("- PnL is assigned to entry cohorts, not exit calendar years.")
    print("- Final forced closures at the last available candle can affect results.")
    print("- This is historical validation, not evidence of live profitability.")


if __name__ == "__main__":
    main()
