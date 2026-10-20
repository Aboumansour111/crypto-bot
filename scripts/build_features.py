import argparse
import time

from app.analysis.technical import build_market_features
from app.db.database import connect, init_db


def get_markets(limit=None):
    with connect() as conn:
        sql = """
            SELECT symbol
            FROM markets
            WHERE exchange='bitpin'
              AND quote_symbol='USDT'
              AND tradable=1
              AND suspended=0
            ORDER BY id
        """

        if limit:
            sql += " LIMIT ?"
            return conn.execute(sql, (limit,)).fetchall()

        return conn.execute(sql).fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    init_db()

    markets = get_markets(args.limit)

    total = len(markets)
    completed = 0
    failed = 0
    total_rows = 0

    print("=" * 80)
    print("FEATURE ENGINE")
    print("=" * 80)
    print("Markets:", total)
    print("Timeframes: 1D, 4h")
    print("=" * 80)

    started = time.time()

    for index, market in enumerate(markets, start=1):
        symbol = market["symbol"]

        print(
            f"[{index}/{total}] {symbol}",
            flush=True,
        )

        market_ok = True

        for timeframe in ("1D", "4h"):
            try:
                rows = build_market_features(
                    symbol=symbol,
                    timeframe=timeframe,
                )

                total_rows += rows

                print(
                    f"  {timeframe}: "
                    f"{rows} rows",
                    flush=True,
                )

            except Exception as exc:
                market_ok = False

                print(
                    f"  {timeframe}: ERROR: {exc}",
                    flush=True,
                )

        if market_ok:
            completed += 1
        else:
            failed += 1

    elapsed = time.time() - started

    print()
    print("=" * 80)
    print("FEATURE ENGINE COMPLETE")
    print("=" * 80)
    print("Successful markets:", completed)
    print("Failed markets:", failed)
    print("Feature rows processed:", total_rows)
    print("Elapsed seconds:", round(elapsed, 2))
    print("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
