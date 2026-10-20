from collections import defaultdict
from datetime import datetime, timezone

from app.backtest.engine import run_backtest


def year_of(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%Y")


def month_of(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%Y-%m")


def analyze(timeframe):
    result = run_backtest(timeframe)
    trades = result["trades"]

    print()
    print("=" * 90)
    print(f"DETAILED BACKTEST ANALYSIS — {timeframe}")
    print("=" * 90)

    # ---------------------------------------------------------
    # 1. Exit reasons
    # ---------------------------------------------------------

    reasons = defaultdict(lambda: {
        "count": 0,
        "pnl": 0.0,
        "wins": 0,
        "losses": 0,
        "fees": 0.0,
    })

    for t in trades:
        r = reasons[t["reason"]]

        r["count"] += 1
        r["pnl"] += t["pnl"]
        r["fees"] += t["fee"]

        if t["pnl"] > 0:
            r["wins"] += 1
        elif t["pnl"] < 0:
            r["losses"] += 1

    print()
    print("EXIT REASONS")
    print("-" * 90)

    print(
        f"{'Reason':<15}"
        f"{'Trades':>10}"
        f"{'Wins':>10}"
        f"{'Losses':>10}"
        f"{'WinRate':>12}"
        f"{'PnL':>18}"
        f"{'Fees':>18}"
    )

    for reason in sorted(reasons):
        r = reasons[reason]

        win_rate = (
            r["wins"] / r["count"] * 100
            if r["count"]
            else 0
        )

        print(
            f"{reason:<15}"
            f"{r['count']:>10,}"
            f"{r['wins']:>10,}"
            f"{r['losses']:>10,}"
            f"{win_rate:>11.2f}%"
            f"{r['pnl']:>18,.2f}"
            f"{r['fees']:>18,.2f}"
        )

    # ---------------------------------------------------------
    # 2. Yearly performance
    # ---------------------------------------------------------

    yearly = defaultdict(lambda: {
        "count": 0,
        "pnl": 0.0,
        "wins": 0,
        "losses": 0,
    })

    for t in trades:
        y = year_of(t["exit_time"])
        d = yearly[y]

        d["count"] += 1
        d["pnl"] += t["pnl"]

        if t["pnl"] > 0:
            d["wins"] += 1
        elif t["pnl"] < 0:
            d["losses"] += 1

    print()
    print("YEARLY TRADE PERFORMANCE")
    print("-" * 90)

    print(
        f"{'Year':<10}"
        f"{'Trades':>10}"
        f"{'Wins':>10}"
        f"{'Losses':>10}"
        f"{'WinRate':>12}"
        f"{'PnL':>20}"
    )

    for year in sorted(yearly):
        d = yearly[year]

        wr = (
            d["wins"] / d["count"] * 100
            if d["count"]
            else 0
        )

        print(
            f"{year:<10}"
            f"{d['count']:>10,}"
            f"{d['wins']:>10,}"
            f"{d['losses']:>10,}"
            f"{wr:>11.2f}%"
            f"{d['pnl']:>20,.2f}"
        )

    # ---------------------------------------------------------
    # 3. Monthly performance
    # ---------------------------------------------------------

    monthly = defaultdict(lambda: {
        "count": 0,
        "pnl": 0.0,
        "wins": 0,
        "losses": 0,
    })

    for t in trades:
        m = month_of(t["exit_time"])
        d = monthly[m]

        d["count"] += 1
        d["pnl"] += t["pnl"]

        if t["pnl"] > 0:
            d["wins"] += 1
        elif t["pnl"] < 0:
            d["losses"] += 1

    print()
    print("MONTHLY TRADE PERFORMANCE")
    print("-" * 90)

    print(
        f"{'Month':<10}"
        f"{'Trades':>10}"
        f"{'Wins':>10}"
        f"{'Losses':>10}"
        f"{'WinRate':>12}"
        f"{'PnL':>20}"
    )

    for month in sorted(monthly):
        d = monthly[month]

        wr = (
            d["wins"] / d["count"] * 100
            if d["count"]
            else 0
        )

        print(
            f"{month:<10}"
            f"{d['count']:>10,}"
            f"{d['wins']:>10,}"
            f"{d['losses']:>10,}"
            f"{wr:>11.2f}%"
            f"{d['pnl']:>20,.2f}"
        )

    # ---------------------------------------------------------
    # 4. Largest winners / losers
    # ---------------------------------------------------------

    ordered = sorted(
        trades,
        key=lambda x: x["pnl"],
    )

    print()
    print("10 LARGEST LOSSES")
    print("-" * 90)

    for t in ordered[:10]:
        print(
            f"{t['symbol']:<18}"
            f"{t['reason']:<12}"
            f"{t['pnl']:>16,.2f}"
        )

    print()
    print("10 LARGEST WINNERS")
    print("-" * 90)

    for t in reversed(ordered[-10:]):
        print(
            f"{t['symbol']:<18}"
            f"{t['reason']:<12}"
            f"{t['pnl']:>16,.2f}"
        )

    print()
    print("=" * 90)


def main():
    for timeframe in ("1D", "4h"):
        analyze(timeframe)


if __name__ == "__main__":
    main()
