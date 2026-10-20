from collections import defaultdict
from datetime import datetime, timezone

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"
TOP_N = 5


def year_of(timestamp):
    return datetime.fromtimestamp(
        int(timestamp), tz=timezone.utc
    ).year


def metrics(trades):
    pnls = [float(t["pnl"]) for t in trades]
    wins = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    return (
        len(pnls),
        sum(pnls),
        sum(p > 0 for p in pnls) / len(pnls) * 100 if pnls else 0,
        wins / losses if losses else None,
    )


def show(label, trades):
    n, pnl, win, pf = metrics(trades)
    pf_text = f"{pf:.3f}" if pf is not None else "-"
    print(
        f"{label:<35} trades={n:>4} "
        f"PnL={pnl:>16,.2f} win={win:>6.2f}% PF={pf_text}"
    )


def main():
    print("Running unchanged filtered backtest...")
    trades = run_variant(TIMEFRAME, filtered=True)["trades"]

    if not trades:
        print("No trades.")
        return

    first_year = min(year_of(t["entry_time"]) for t in trades)
    last_year = max(year_of(t["entry_time"]) for t in trades)

    for test_year in range(first_year + 1, last_year + 1):
        train_start = int(datetime(
            test_year - 1, 1, 1, tzinfo=timezone.utc
        ).timestamp())
        test_start = int(datetime(
            test_year, 1, 1, tzinfo=timezone.utc
        ).timestamp())
        test_end = int(datetime(
            test_year + 1, 1, 1, tzinfo=timezone.utc
        ).timestamp())

        # Training: entered in previous calendar year and closed
        # before the test year begins.
        training = [
            t for t in trades
            if train_start <= int(t["entry_time"]) < test_start
            and int(t["exit_time"]) < test_start
        ]

        if not training:
            print(f"\n{test_year}: no eligible training trades; skipped.")
            continue

        train_pnl = defaultdict(float)
        train_count = defaultdict(int)
        for t in training:
            train_pnl[t["symbol"]] += float(t["pnl"])
            train_count[t["symbol"]] += 1

        ranked = sorted(
            train_pnl.items(), key=lambda x: x[1], reverse=True
        )
        selected = {
            symbol for symbol, pnl in ranked[:TOP_N] if pnl > 0
        }

        # Test: entries in this calendar year, with exits before
        # the next calendar year. Boundary-crossing trades are excluded.
        entered_test_year = [
            t for t in trades
            if test_start <= int(t["entry_time"]) < test_end
        ]
        test_trades = [
            t for t in entered_test_year
            if int(t["exit_time"]) < test_end
        ]
        boundary_excluded = len(entered_test_year) - len(test_trades)

        selected_trades = [
            t for t in test_trades if t["symbol"] in selected
        ]
        other_trades = [
            t for t in test_trades if t["symbol"] not in selected
        ]

        print("\n" + "=" * 85)
        print(f"TRAIN: {test_year - 1} | TEST: {test_year}")
        print(f"Eligible training trades: {len(training)}")
        print(f"Test-year entries: {len(entered_test_year)}")
        print(f"Boundary-crossing trades excluded: {boundary_excluded}")
        print("Selected symbols (based only on eligible prior-year trades):")

        for symbol, pnl in ranked[:TOP_N]:
            print(
                f"  {symbol:<20} train_pnl={pnl:>14,.2f} "
                f"train_trades={train_count[symbol]}"
            )

        show("ALL eligible test trades", test_trades)
        show("SELECTED symbols only", selected_trades)
        show("OTHER symbols", other_trades)

    print("\nNote: the latest year may be incomplete.")
    print("This test is diagnostic, not a guarantee of future profitability.")


if __name__ == "__main__":
    main()
