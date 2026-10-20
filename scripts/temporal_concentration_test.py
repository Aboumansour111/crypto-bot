from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"


def period_of(timestamp: int) -> tuple[str, str]:
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    year = str(dt.year)
    half = "H1" if dt.month <= 6 else "H2"
    return year, f"{dt.year}-{half}"


def fmt(value: float) -> str:
    return f"{value:,.2f}"


def main() -> None:
    print("Running unchanged FILTERED backtest...")
    result = run_variant(TIMEFRAME, filtered=True)
    trades = result["trades"]

    if not trades:
        print("No trades returned.")
        return

    yearly_symbol = defaultdict(float)
    yearly_symbol_count = defaultdict(int)
    halfyear_symbol = defaultdict(float)
    halfyear_symbol_count = defaultdict(int)
    symbol_total = defaultdict(float)
    symbol_count = defaultdict(int)
    yearly_total = defaultdict(float)
    halfyear_total = defaultdict(float)

    for trade in trades:
        symbol = trade["symbol"]
        pnl = float(trade["pnl"])
        year, halfyear = period_of(int(trade["entry_time"]))

        yearly_symbol[(year, symbol)] += pnl
        yearly_symbol_count[(year, symbol)] += 1
        halfyear_symbol[(halfyear, symbol)] += pnl
        halfyear_symbol_count[(halfyear, symbol)] += 1
        symbol_total[symbol] += pnl
        symbol_count[symbol] += 1
        yearly_total[year] += pnl
        halfyear_total[halfyear] += pnl

    print("\n" + "=" * 100)
    print("YEARLY PERFORMANCE")
    print("=" * 100)
    for year in sorted(yearly_total):
        print(f"{year}: PnL={fmt(yearly_total[year])}")

        ranked = sorted(
            ((sym, pnl) for (yr, sym), pnl in yearly_symbol.items()
             if yr == year),
            key=lambda item: item[1],
            reverse=True,
        )

        print("  TOP 10 SYMBOLS:")
        for symbol, pnl in ranked[:10]:
            count = yearly_symbol_count[(year, symbol)]
            print(f"    {symbol:<20} PnL={fmt(pnl):>16}  trades={count}")

        print("  BOTTOM 5 SYMBOLS:")
        for symbol, pnl in ranked[-5:][::-1]:
            count = yearly_symbol_count[(year, symbol)]
            print(f"    {symbol:<20} PnL={fmt(pnl):>16}  trades={count}")

    print("\n" + "=" * 100)
    print("HALF-YEAR PERFORMANCE")
    print("=" * 100)
    for halfyear in sorted(halfyear_total):
        print(f"\n{halfyear}: PnL={fmt(halfyear_total[halfyear])}")
        ranked = sorted(
            ((sym, pnl) for (period, sym), pnl in halfyear_symbol.items()
             if period == halfyear),
            key=lambda item: item[1],
            reverse=True,
        )
        for symbol, pnl in ranked[:5]:
            count = halfyear_symbol_count[(halfyear, symbol)]
            print(f"  {symbol:<20} PnL={fmt(pnl):>16}  trades={count}")

    print("\n" + "=" * 100)
    print("SYMBOL CONSISTENCY ACROSS YEARS")
    print("=" * 100)
    years = sorted(yearly_total)
    consistency = []

    for symbol, total in symbol_total.items():
        values = [yearly_symbol.get((year, symbol), 0.0) for year in years]
        active_years = sum(
            1 for year in years if yearly_symbol_count.get((year, symbol), 0)
        )
        positive_years = sum(1 for value in values if value > 0)
        consistency.append(
            (positive_years, active_years, total, symbol, values)
        )

    for positive, active, total, symbol, values in sorted(
        consistency, key=lambda row: (row[0], row[2]), reverse=True
    )[:25]:
        yearly_text = " | ".join(
            f"{year}:{fmt(value)}" for year, value in zip(years, values)
        )
        print(
            f"{symbol:<20} total={fmt(total):>16} "
            f"positive_years={positive}/{active} | {yearly_text}"
        )

    print("\n" + "=" * 100)
    print("LARGEST INDIVIDUAL TRADES")
    print("=" * 100)
    sorted_trades = sorted(
        trades, key=lambda trade: float(trade["pnl"]), reverse=True
    )
    total_pnl = sum(float(trade["pnl"]) for trade in trades)
    positive_pnl = sum(
        float(trade["pnl"]) for trade in trades
        if float(trade["pnl"]) > 0
    )

    print(f"Total trades: {len(trades)}")
    print(f"Total net PnL: {fmt(total_pnl)}")
    print(f"Gross positive PnL: {fmt(positive_pnl)}")

    for n in (1, 5, 10, 20):
        selected = sorted_trades[:n]
        contribution = sum(float(t["pnl"]) for t in selected)
        print(
            f"Top {n:>2} trades: PnL={fmt(contribution):>16} "
            f"share_of_gross_profit="
            f"{(contribution / positive_pnl * 100 if positive_pnl else 0):.2f}%"
        )

    for i, trade in enumerate(sorted_trades[:20], 1):
        dt = datetime.fromtimestamp(
            int(trade["entry_time"]), tz=timezone.utc
        ).strftime("%Y-%m-%d")
        print(
            f"{i:>2}. {dt} {trade['symbol']:<20} "
            f"PnL={fmt(float(trade['pnl'])):>16}"
        )


if __name__ == "__main__":
    main()
