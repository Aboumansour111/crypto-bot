from datetime import datetime, timezone, timedelta

from app.db.database import connect
from app.exchanges.bitpin import BitpinClient


RESOLUTION_SECONDS = {
    "1D": 86400,
    "4h": 4 * 3600,
}

MAX_CANDLES_PER_REQUEST = 9000


def _normalize_resolution(resolution: str) -> str:
    if resolution not in RESOLUTION_SECONDS:
        raise ValueError(
            f"Unsupported resolution: {resolution}. "
            f"Supported: {list(RESOLUTION_SECONDS)}"
        )
    return resolution


def collect_history(
    symbol: str,
    resolution: str,
    start_ts: int,
    end_ts: int,
) -> int:
    resolution = _normalize_resolution(resolution)

    if start_ts >= end_ts:
        return 0

    client = BitpinClient()
    interval = RESOLUTION_SECONDS[resolution]

    total_written = 0
    cursor = start_ts

    while cursor < end_ts:
        chunk_end = min(
            end_ts,
            cursor + interval * MAX_CANDLES_PER_REQUEST,
        )

        bars = client.get_bars(
            symbol=symbol,
            resolution=resolution,
            from_ts=cursor,
            to_ts=chunk_end,
        )

        if not bars:
            cursor = chunk_end + 1
            continue

        with connect() as conn:
            market = conn.execute(
                """
                SELECT id
                FROM markets
                WHERE exchange = 'bitpin'
                  AND symbol = ?
                """,
                (symbol,),
            ).fetchone()

            if market is None:
                raise ValueError(
                    f"Market not found in DB: {symbol}"
                )

            market_id = market["id"]

            for bar in bars:
                ts = int(bar["ts"])

                if ts < start_ts or ts > end_ts:
                    continue

                conn.execute(
                    """
                    INSERT INTO ohlcv (
                        market_id,
                        timeframe,
                        timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)

                    ON CONFLICT(
                        market_id,
                        timeframe,
                        timestamp
                    )
                    DO UPDATE SET
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        volume = excluded.volume
                    """,
                    (
                        market_id,
                        resolution,
                        ts,
                        float(bar["open"]),
                        float(bar["high"]),
                        float(bar["low"]),
                        float(bar["close"]),
                        float(bar["volume"]),
                    ),
                )

                total_written += 1

            conn.commit()

        last_ts = max(int(bar["ts"]) for bar in bars)

        next_cursor = last_ts + interval

        if next_cursor <= cursor:
            raise RuntimeError(
                f"Collector cursor did not advance: "
                f"{symbol} {resolution} cursor={cursor}"
            )

        cursor = next_cursor

    return total_written


def collect_last_days(
    symbol: str,
    resolution: str,
    days: int,
) -> int:
    now = datetime.now(timezone.utc)
    end_ts = int(now.timestamp())
    start_ts = int(
        (now - timedelta(days=days)).timestamp()
    )

    return collect_history(
        symbol=symbol,
        resolution=resolution,
        start_ts=start_ts,
        end_ts=end_ts,
    )
