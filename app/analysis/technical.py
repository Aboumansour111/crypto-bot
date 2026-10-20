from math import sqrt
from app.db.database import connect


def sma(values, period):
    result = [None] * len(values)

    if len(values) < period:
        return result

    total = sum(values[:period])
    result[period - 1] = total / period

    for i in range(period, len(values)):
        total += values[i]
        total -= values[i - period]
        result[i] = total / period

    return result


def ema(values, period):
    result = [None] * len(values)

    if len(values) < period:
        return result

    seed = sum(values[:period]) / period
    result[period - 1] = seed

    alpha = 2 / (period + 1)
    previous = seed

    for i in range(period, len(values)):
        current = (
            values[i] * alpha
            + previous * (1 - alpha)
        )
        result[i] = current
        previous = current

    return result


def returns(values, period):
    result = [None] * len(values)

    for i in range(period, len(values)):
        previous = values[i - period]

        if previous != 0:
            result[i] = (
                values[i] / previous
            ) - 1

    return result


def roc(values, period):
    return returns(values, period)


def rsi(values, period=14):
    result = [None] * len(values)

    if len(values) <= period:
        return result

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]

        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def calculate(index, gain, loss):
        if loss == 0:
            return 100.0

        rs = gain / loss
        return 100 - (100 / (1 + rs))

    result[period] = calculate(
        period,
        avg_gain,
        avg_loss,
    )

    for i in range(period + 1, len(values)):
        gain = gains[i - 1]
        loss = losses[i - 1]

        avg_gain = (
            (avg_gain * (period - 1)) + gain
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) + loss
        ) / period

        result[i] = calculate(
            i,
            avg_gain,
            avg_loss,
        )

    return result


def true_ranges(high, low, close):
    result = [None] * len(close)

    if not close:
        return result

    result[0] = high[0] - low[0]

    for i in range(1, len(close)):
        result[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    return result


def atr(high, low, close, period=14):
    tr = true_ranges(high, low, close)
    result = [None] * len(close)

    if len(close) < period:
        return result

    seed = sum(tr[:period]) / period
    result[period - 1] = seed

    previous = seed

    for i in range(period, len(close)):
        current = (
            (previous * (period - 1)) + tr[i]
        ) / period

        result[i] = current
        previous = current

    return result


def realized_volatility(values, period=20):
    result = [None] * len(values)

    log_returns = [None] * len(values)

    for i in range(1, len(values)):
        if values[i - 1] > 0 and values[i] > 0:
            import math

            log_returns[i] = math.log(
                values[i] / values[i - 1]
            )

    for i in range(period, len(values)):
        window = [
            x for x in log_returns[
                i - period + 1:i + 1
            ]
            if x is not None
        ]

        if len(window) == period:
            mean = sum(window) / period

            variance = sum(
                (x - mean) ** 2
                for x in window
            ) / period

            result[i] = sqrt(variance)

    return result


def volume_ratio(volumes, period=20):
    result = [None] * len(volumes)
    averages = sma(volumes, period)

    for i in range(len(volumes)):
        if (
            averages[i] is not None
            and averages[i] != 0
        ):
            result[i] = (
                volumes[i] / averages[i]
            )

    return result


def build_features(rows):
    if not rows:
        return []

    close = [float(r["close"]) for r in rows]
    high = [float(r["high"]) for r in rows]
    low = [float(r["low"]) for r in rows]
    volume = [float(r["volume"]) for r in rows]

    sma20 = sma(close, 20)
    sma50 = sma(close, 50)
    sma200 = sma(close, 200)

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)

    rsi14 = rsi(close, 14)

    roc7 = roc(close, 7)
    roc14 = roc(close, 14)
    roc30 = roc(close, 30)

    ret1 = returns(close, 1)
    ret7 = returns(close, 7)
    ret14 = returns(close, 14)
    ret30 = returns(close, 30)

    atr14 = atr(
        high,
        low,
        close,
        14,
    )

    vol_ratio = volume_ratio(
        volume,
        20,
    )

    realized_vol = realized_volatility(
        close,
        20,
    )

    features = []

    for i, row in enumerate(rows):
        atr_value = atr14[i]

        atr_pct = None

        if (
            atr_value is not None
            and close[i] != 0
        ):
            atr_pct = (
                atr_value / close[i]
            )

        features.append({
            "market_id": row["market_id"],
            "timeframe": row["timeframe"],
            "timestamp": row["timestamp"],

            "sma_20": sma20[i],
            "sma_50": sma50[i],
            "sma_200": sma200[i],

            "ema_20": ema20[i],
            "ema_50": ema50[i],
            "ema_200": ema200[i],

            "rsi_14": rsi14[i],

            "roc_7": roc7[i],
            "roc_14": roc14[i],
            "roc_30": roc30[i],

            "atr_14": atr_value,
            "atr_pct_14": atr_pct,

            "return_1": ret1[i],
            "return_7": ret7[i],
            "return_14": ret14[i],
            "return_30": ret30[i],

            "volume_sma_20": (
                sma(volume, 20)[i]
            ),
            "volume_ratio_20": vol_ratio[i],

            "realized_vol_20": realized_vol[i],
        })

    return features


def build_market_features(
    symbol: str,
    timeframe: str,
):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                ohlcv.id AS source_id,
                market_id,
                timeframe,
                timestamp,
                open,
                high,
                low,
                close,
                volume
            FROM ohlcv
            JOIN markets
              ON markets.id = ohlcv.market_id
            WHERE markets.symbol = ?
              AND ohlcv.timeframe = ?
            ORDER BY timestamp
            """,
            (symbol, timeframe),
        ).fetchall()

        if not rows:
            raise ValueError(
                f"No OHLCV data: {symbol} {timeframe}"
            )

        features = build_features(rows)

        for feature in features:
            conn.execute(
                """
                INSERT INTO features (
                    market_id,
                    timeframe,
                    timestamp,
                    sma_20,
                    sma_50,
                    sma_200,
                    ema_20,
                    ema_50,
                    ema_200,
                    rsi_14,
                    roc_7,
                    roc_14,
                    roc_30,
                    atr_14,
                    atr_pct_14,
                    return_1,
                    return_7,
                    return_14,
                    return_30,
                    volume_sma_20,
                    volume_ratio_20,
                    realized_vol_20
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(
                    market_id,
                    timeframe,
                    timestamp
                )
                DO UPDATE SET
                    sma_20 = excluded.sma_20,
                    sma_50 = excluded.sma_50,
                    sma_200 = excluded.sma_200,
                    ema_20 = excluded.ema_20,
                    ema_50 = excluded.ema_50,
                    ema_200 = excluded.ema_200,
                    rsi_14 = excluded.rsi_14,
                    roc_7 = excluded.roc_7,
                    roc_14 = excluded.roc_14,
                    roc_30 = excluded.roc_30,
                    atr_14 = excluded.atr_14,
                    atr_pct_14 = excluded.atr_pct_14,
                    return_1 = excluded.return_1,
                    return_7 = excluded.return_7,
                    return_14 = excluded.return_14,
                    return_30 = excluded.return_30,
                    volume_sma_20 = excluded.volume_sma_20,
                    volume_ratio_20 = excluded.volume_ratio_20,
                    realized_vol_20 = excluded.realized_vol_20,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    feature["market_id"],
                    feature["timeframe"],
                    feature["timestamp"],
                    feature["sma_20"],
                    feature["sma_50"],
                    feature["sma_200"],
                    feature["ema_20"],
                    feature["ema_50"],
                    feature["ema_200"],
                    feature["rsi_14"],
                    feature["roc_7"],
                    feature["roc_14"],
                    feature["roc_30"],
                    feature["atr_14"],
                    feature["atr_pct_14"],
                    feature["return_1"],
                    feature["return_7"],
                    feature["return_14"],
                    feature["return_30"],
                    feature["volume_sma_20"],
                    feature["volume_ratio_20"],
                    feature["realized_vol_20"],
                ),
            )

        conn.commit()

        return len(features)
