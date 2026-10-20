from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config.settings import settings
from app.strategy.scoring import STRATEGY_VERSION


DB_PATH = settings.db_path

INITIAL_CAPITAL = 100_000_000.0
RISK_PER_TRADE = 0.01
MAX_POSITION_WEIGHT = 0.20
MAX_CONCURRENT_POSITIONS = 5

FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005

MAX_HOLD_BARS = {
    "1D": 20,
    "4h": 30,
}


@dataclass
class Position:
    market_id: int
    symbol: str
    entry_index: int
    entry_time: int
    entry_price: float
    quantity: float
    stop_loss: float
    target1: float
    target2: float
    remaining_quantity: float
    target1_hit: bool = False


def load_data(conn, timeframe):
    markets = {
        row[0]: row[1]
        for row in conn.execute("""
            SELECT id, symbol
            FROM markets
            WHERE quote_symbol='USDT'
        """)
    }

    bars = {}

    rows = conn.execute("""
        SELECT market_id, timestamp, open, high, low, close
        FROM ohlcv
        WHERE timeframe=?
        ORDER BY market_id, timestamp
    """, (timeframe,)).fetchall()

    for market_id, ts, op, high, low, close in rows:
        bars.setdefault(market_id, []).append(
            (
                ts,
                float(op),
                float(high),
                float(low),
                float(close),
            )
        )

    return markets, bars


def load_signals(conn, timeframe):
    rows = conn.execute("""
        SELECT
            market_id,
            timestamp,
            rank,
            score,
            entry_price,
            stop_loss,
            target1,
            target2
        FROM signals
        WHERE timeframe=?
          AND strategy_version=?
          AND signal='BUY'
        ORDER BY timestamp, rank
    """, (timeframe, STRATEGY_VERSION)).fetchall()

    return {
        (row[0], row[1]): row[2:]
        for row in rows
    }


def apply_exit(
    pos,
    exit_price,
    exit_time,
    reason,
    quantity,
    cash,
    trades,
    reference_price,
):
    if quantity <= 0:
        return cash

    gross = quantity * exit_price
    exit_fee = gross * FEE_RATE

    cash += gross - exit_fee

    entry_cost = quantity * pos.entry_price
    entry_fee = entry_cost * FEE_RATE

    pnl = (
        gross
        - exit_fee
        - entry_cost
        - entry_fee
    )

    slippage_cost = (
        abs(exit_price - reference_price) * quantity
    )

    trades.append({
        "market_id": pos.market_id,
        "symbol": pos.symbol,
        "entry_time": pos.entry_time,
        "exit_time": exit_time,
        "entry_price": pos.entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "reason": reason,
        "gross_value": gross,
        "fee": exit_fee + entry_fee,
        "slippage_cost": slippage_cost,
        "pnl": pnl,
    })

    return cash


def run_backtest(timeframe: str):
    if timeframe not in ("1D", "4h"):
        raise ValueError(timeframe)

    conn = sqlite3.connect(DB_PATH)

    markets, bars = load_data(conn, timeframe)
    signals = load_signals(conn, timeframe)

    conn.close()

    # ---------------------------------------------------------
    # Per-market lookup
    # ---------------------------------------------------------

    bar_lookup = {}
    index_lookup = {}

    for market_id, series in bars.items():
        bar_lookup[market_id] = {
            row[0]: row[1:]
            for row in series
        }

        index_lookup[market_id] = {
            row[0]: i
            for i, row in enumerate(series)
        }

    # ---------------------------------------------------------
    # Global timeline
    # ---------------------------------------------------------

    timestamps = sorted({
        ts
        for series in bars.values()
        for ts, *_ in series
    })

    if not timestamps:
        raise RuntimeError(
            f"No OHLCV data for timeframe={timeframe}"
        )

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    cash = INITIAL_CAPITAL
    positions: list[Position] = []

    trades = []
    equity_curve = []

    total_fees = 0.0
    total_turnover = 0.0
    total_slippage = 0.0

    # ---------------------------------------------------------
    # Main simulation
    # ---------------------------------------------------------

    for current_ts in timestamps:

        # =====================================================
        # 1. Manage open positions
        # =====================================================

        survivors = []

        for pos in positions:

            current_index = index_lookup[pos.market_id].get(
                current_ts
            )

            if current_index is None:
                survivors.append(pos)
                continue

            bar = bar_lookup[pos.market_id].get(current_ts)

            if bar is None:
                survivors.append(pos)
                continue

            op, high, low, close = bar

            bars_held = (
                current_index - pos.entry_index
            )

            # -------------------------------------------------
            # STOP
            # -------------------------------------------------
            #
            # Conservative assumption:
            # if stop and target are both touched in the
            # same candle, STOP happens first.
            #
            if low <= pos.stop_loss:

                quantity = pos.remaining_quantity

                exit_price = (
                    pos.stop_loss
                    * (1 - SLIPPAGE_RATE)
                )

                before = len(trades)

                cash = apply_exit(
                    pos,
                    exit_price,
                    current_ts,
                    "STOP",
                    quantity,
                    cash,
                    trades,
                    pos.stop_loss,
                )

                if len(trades) > before:
                    trade = trades[-1]

                    total_fees += trade["fee"]

                    total_turnover += (
                        quantity * pos.entry_price
                        + quantity * exit_price
                    )

                    total_slippage += (
                        trade["slippage_cost"]
                    )

                continue

            # -------------------------------------------------
            # TARGET 1
            # -------------------------------------------------
            #
            # If T1 was not hit and this candle reaches T2,
            # price necessarily passed T1 first.
            #
            if (
                not pos.target1_hit
                and high >= pos.target1
            ):

                quantity = (
                    pos.remaining_quantity * 0.50
                )

                exit_price = (
                    pos.target1
                    * (1 - SLIPPAGE_RATE)
                )

                before = len(trades)

                cash = apply_exit(
                    pos,
                    exit_price,
                    current_ts,
                    "TARGET1",
                    quantity,
                    cash,
                    trades,
                    pos.target1,
                )

                if len(trades) > before:
                    trade = trades[-1]

                    total_fees += trade["fee"]

                    total_turnover += (
                        quantity * pos.entry_price
                        + quantity * exit_price
                    )

                    total_slippage += (
                        trade["slippage_cost"]
                    )

                pos.remaining_quantity -= quantity
                pos.target1_hit = True

            # -------------------------------------------------
            # TARGET 2
            # -------------------------------------------------
            #
            # Remaining quantity exits at T2.
            #
            if (
                pos.target1_hit
                and pos.remaining_quantity > 0
                and high >= pos.target2
            ):

                quantity = pos.remaining_quantity

                exit_price = (
                    pos.target2
                    * (1 - SLIPPAGE_RATE)
                )

                before = len(trades)

                cash = apply_exit(
                    pos,
                    exit_price,
                    current_ts,
                    "TARGET2",
                    quantity,
                    cash,
                    trades,
                    pos.target2,
                )

                if len(trades) > before:
                    trade = trades[-1]

                    total_fees += trade["fee"]

                    total_turnover += (
                        quantity * pos.entry_price
                        + quantity * exit_price
                    )

                    total_slippage += (
                        trade["slippage_cost"]
                    )

                pos.remaining_quantity = 0.0

                continue

            # -------------------------------------------------
            # TIME EXIT
            # -------------------------------------------------

            if bars_held >= MAX_HOLD_BARS[timeframe]:

                quantity = pos.remaining_quantity

                exit_price = (
                    close
                    * (1 - SLIPPAGE_RATE)
                )

                before = len(trades)

                cash = apply_exit(
                    pos,
                    exit_price,
                    current_ts,
                    "TIME_EXIT",
                    quantity,
                    cash,
                    trades,
                    close,
                )

                if len(trades) > before:
                    trade = trades[-1]

                    total_fees += trade["fee"]

                    total_turnover += (
                        quantity * pos.entry_price
                        + quantity * exit_price
                    )

                    total_slippage += (
                        trade["slippage_cost"]
                    )

                continue

            survivors.append(pos)

        positions = survivors

        # =====================================================
        # 2. New entries
        # =====================================================

        available_slots = (
            MAX_CONCURRENT_POSITIONS
            - len(positions)
        )

        if available_slots > 0:

            candidates = []

            for market_id, symbol in markets.items():

                sig = signals.get(
                    (market_id, current_ts)
                )

                if sig is None:
                    continue

                (
                    rank,
                    score,
                    entry_price_signal,
                    stop,
                    target1,
                    target2,
                ) = sig

                series = bars.get(market_id)

                if not series:
                    continue

                current_index = index_lookup[
                    market_id
                ].get(current_ts)

                if current_index is None:
                    continue

                next_index = current_index + 1

                if next_index >= len(series):
                    continue

                next_bar = series[next_index]

                next_ts = next_bar[0]
                next_open = next_bar[1]

                if (
                    stop is None
                    or target1 is None
                    or target2 is None
                ):
                    continue

                candidates.append((
                    rank,
                    -score,
                    market_id,
                    symbol,
                    next_index,
                    next_ts,
                    next_open,
                    float(stop),
                    float(target1),
                    float(target2),
                ))

            candidates.sort()

            for candidate in candidates:

                if len(positions) >= MAX_CONCURRENT_POSITIONS:
                    break

                (
                    rank,
                    neg_score,
                    market_id,
                    symbol,
                    entry_index,
                    entry_time,
                    entry_price,
                    stop,
                    target1,
                    target2,
                ) = candidate

                if any(
                    p.market_id == market_id
                    for p in positions
                ):
                    continue

                if entry_price <= stop:
                    continue

                stop_distance = (
                    entry_price - stop
                )

                risk_amount = (
                    cash * RISK_PER_TRADE
                )

                quantity_by_risk = (
                    risk_amount
                    / stop_distance
                )

                max_value = (
                    cash
                    * MAX_POSITION_WEIGHT
                )

                quantity_by_weight = (
                    max_value
                    / entry_price
                )

                quantity = min(
                    quantity_by_risk,
                    quantity_by_weight,
                )

                if quantity <= 0:
                    continue

                gross = quantity * entry_price
                fee = gross * FEE_RATE
                total_cost = gross + fee

                if total_cost > cash:

                    quantity = (
                        cash
                        / (
                            entry_price
                            * (1 + FEE_RATE)
                        )
                    )

                    gross = quantity * entry_price
                    fee = gross * FEE_RATE
                    total_cost = gross + fee

                if quantity <= 0:
                    continue

                cash -= total_cost

                total_fees += fee
                total_turnover += gross

                positions.append(
                    Position(
                        market_id=market_id,
                        symbol=symbol,
                        entry_index=entry_index,
                        entry_time=entry_time,
                        entry_price=entry_price,
                        quantity=quantity,
                        stop_loss=stop,
                        target1=target1,
                        target2=target2,
                        remaining_quantity=quantity,
                    )
                )

        # =====================================================
        # 3. Mark-to-market
        # =====================================================

        equity = cash

        for pos in positions:

            bar = bar_lookup[
                pos.market_id
            ].get(current_ts)

            if bar is not None:

                close = bar[3]

                equity += (
                    pos.remaining_quantity
                    * close
                )

        equity_curve.append(
            (current_ts, equity)
        )

    # ---------------------------------------------------------
    # Force close at final available candle
    # ---------------------------------------------------------

    final_ts = timestamps[-1]

    for pos in positions:

        bar = bar_lookup[
            pos.market_id
        ].get(final_ts)

        if bar is None:
            continue

        close = bar[3]

        exit_price = (
            close
            * (1 - SLIPPAGE_RATE)
        )

        quantity = pos.remaining_quantity

        before = len(trades)

        cash = apply_exit(
            pos,
            exit_price,
            final_ts,
            "FINAL",
            quantity,
            cash,
            trades,
            close,
        )

        if len(trades) > before:

            trade = trades[-1]

            total_fees += trade["fee"]

            total_turnover += (
                quantity * pos.entry_price
                + quantity * exit_price
            )

            total_slippage += (
                trade["slippage_cost"]
            )

    # ---------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------

    final_equity = cash

    total_return = (
        final_equity / INITIAL_CAPITAL - 1
    ) * 100

    peak = INITIAL_CAPITAL
    max_drawdown = 0.0

    for _, equity in equity_curve:

        if equity > peak:
            peak = equity

        drawdown = (
            equity / peak - 1
        ) * 100

        if drawdown < max_drawdown:
            max_drawdown = drawdown

    closed_trades = trades

    wins = [
        t
        for t in closed_trades
        if t["pnl"] > 0
    ]

    losses = [
        t
        for t in closed_trades
        if t["pnl"] < 0
    ]

    gross_profit = sum(
        t["pnl"]
        for t in wins
    )

    gross_loss = abs(sum(
        t["pnl"]
        for t in losses
    ))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    win_rate = (
        len(wins)
        / len(closed_trades)
        * 100
        if closed_trades
        else 0
    )

    average_trade = (
        sum(t["pnl"] for t in closed_trades)
        / len(closed_trades)
        if closed_trades
        else 0
    )

    # ---------------------------------------------------------
    # Monthly equity
    # ---------------------------------------------------------

    monthly = {}

    for ts, equity in equity_curve:

        dt = __import__(
            "datetime"
        ).datetime.fromtimestamp(
            ts,
            tz=__import__(
                "datetime"
            ).timezone.utc,
        )

        month = dt.strftime("%Y-%m")

        monthly[month] = equity

    monthly_returns = {}

    previous_equity = INITIAL_CAPITAL

    for month in sorted(monthly):

        equity = monthly[month]

        monthly_returns[month] = (
            equity / previous_equity - 1
        ) * 100

        previous_equity = equity

    return {
        "timeframe": timeframe,
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": final_equity,
        "return_pct": total_return,
        "max_drawdown_pct": max_drawdown,
        "trades": closed_trades,
        "trade_count": len(closed_trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "average_trade": average_trade,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_fees": total_fees,
        "total_turnover": total_turnover,
        "total_slippage": total_slippage,
        "monthly_returns": monthly_returns,
    }
