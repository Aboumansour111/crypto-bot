from collections import defaultdict
from datetime import datetime, timezone

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"
TOP_N = 5


def year_of(trade):
    return datetime.fromtimestamp(
        int(trade["entry_time"]), tz=timezone.utc
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
        f"{label:<34} trades={n:>4} "
        f"PnL={pnl:>16,.2f} win={win:>6.2f}% PF={pf_text}"
    )


def main():
    print("Running filtered backtest without strategy changes...")
    trades = run_variant(TIMEFRAME, filtered=True)["trades"]

    by_year_symbol = defaultdict(float)
    by_year_trades = defaultdict(list)

    for trade in trades:
        year = year_of(trade)
        by_year_symbol[(year, trade["symbol"])] += float(trade["pnl"])
        by_year_trades[year].append(trade)

    years = sorted(by_year_trades)

    print("\nWALK-FORWARD SYMBOL SELECTION")
    print("Select top symbols using year N; evaluate only in year N+1.")
    print("No symbol is selected using the evaluation year's PnL.")

    for train_year, test_year in zip(years, years[1:]):
        ranked = sorted(
            (
                (symbol, pnl)
                for (year, symbol), pnl in by_year_symbol.items()
                if year == train_year
            ),
            key=lambda x: x[1],
            reverse=True,
        )
        selected = {symbol for symbol, pnl in ranked[:TOP_N] if pnl > 0}

        test_trades = by_year_trades[test_year]
        selected_trades = [
            t for t in test_trades if t["symbol"] in selected
        ]

        print(f"\n{'=' * 78}")
        print(f"TRAIN YEAR: {train_year} | TEST YEAR: {test_year}")
        print("Selected symbols from training year:")
        for symbol, pnl in ranked[:TOP_N]:
            print(f"  {symbol:<20} training PnL={pnl:>14,.2f}")

        show("ALL SYMBOLS in test year", test_trades)
        show("SELECTED SYMBOLS only", selected_trades)

        excluded_trades = [
            t for t in test_trades if t["symbol"] not in selected
        ]
        show("OTHER SYMBOLS", excluded_trades)

    print("\nImportant: this is a diagnostic backtest, not proof of live profitability.")
    print("It does not account for selection uncertainty or guarantee executable fills.")


if __name__ == "__main__":
    main()
