import argparse
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from app.collector.historical import collect_last_days
from app.db.database import connect, init_db


def get_markets(limit: int | None = None):
    with connect() as conn:
        sql = """
            SELECT id, symbol
            FROM markets
            WHERE exchange = 'bitpin'
              AND quote_symbol = 'USDT'
              AND tradable = 1
              AND suspended = 0
            ORDER BY id
        """

        if limit is not None:
            sql += " LIMIT ?"
            rows = conn.execute(sql, (limit,)).fetchall()
        else:
            rows = conn.execute(sql).fetchall()

    return rows


def create_run(job: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO collection_runs (
                job,
                status,
                rows_written
            )
            VALUES (?, 'RUNNING', 0)
            """,
            (job,),
        )
        conn.commit()
        return cur.lastrowid


def finish_run(
    run_id: int,
    status: str,
    rows_written: int,
    error: str | None = None,
):
    with connect() as conn:
        conn.execute(
            """
            UPDATE collection_runs
            SET finished_at = CURRENT_TIMESTAMP,
                status = ?,
                rows_written = ?,
                error = ?
            WHERE id = ?
            """,
            (status, rows_written, error, run_id),
        )
        conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Collect Bitpin historical OHLCV data."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of markets to process.",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=730,
        help="Number of historical days.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries per market/timeframe.",
    )

    args = parser.parse_args()

    init_db()

    markets = get_markets(args.limit)

    if not markets:
        print("No markets found.")
        return 1

    print("=" * 80)
    print("HISTORICAL COLLECTION")
    print("=" * 80)
    print(f"Markets : {len(markets)}")
    print(f"Days    : {args.days}")
    print("TFs     : 1D, 4h")
    print("=" * 80)

    job = (
        f"historical_{args.days}d_"
        f"{len(markets)}markets"
    )

    run_id = create_run(job)

    total_written = 0
    success = 0
    failed = 0
    failures = []

    try:
        for index, market in enumerate(markets, start=1):
            symbol = market["symbol"]

            print()
            print(
                f"[{index}/{len(markets)}] "
                f"{symbol}"
            )

            market_ok = True

            for resolution in ("1D", "4h"):
                completed = False
                last_error = None

                for attempt in range(1, args.retries + 1):
                    try:
                        print(
                            f"  {resolution}: "
                            f"attempt {attempt}/{args.retries}"
                        )

                        written = collect_last_days(
                            symbol=symbol,
                            resolution=resolution,
                            days=args.days,
                        )

                        print(
                            f"  {resolution}: "
                            f"WRITTEN={written}"
                        )

                        total_written += written
                        completed = True
                        break

                    except Exception as exc:
                        last_error = str(exc)

                        print(
                            f"  {resolution}: ERROR: "
                            f"{last_error}"
                        )

                        if attempt < args.retries:
                            time.sleep(3)

                if not completed:
                    market_ok = False
                    failures.append(
                        f"{symbol} {resolution}: {last_error}"
                    )

            if market_ok:
                success += 1
            else:
                failed += 1

            print(
                f"  RESULT: "
                f"{'OK' if market_ok else 'FAILED'}"
            )

        status = "SUCCESS" if failed == 0 else "PARTIAL"

        finish_run(
            run_id=run_id,
            status=status,
            rows_written=total_written,
            error=(
                "\n".join(failures)
                if failures
                else None
            ),
        )

    except Exception as exc:
        finish_run(
            run_id=run_id,
            status="FAILED",
            rows_written=total_written,
            error=str(exc),
        )
        raise

    print()
    print("=" * 80)
    print("COLLECTION COMPLETE")
    print("=" * 80)
    print(f"Successful markets : {success}")
    print(f"Failed markets     : {failed}")
    print(f"Rows written       : {total_written}")

    if failures:
        print()
        print("FAILURES:")
        for failure in failures:
            print(f" - {failure}")

    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
