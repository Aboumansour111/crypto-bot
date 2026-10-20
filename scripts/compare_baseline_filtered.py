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


def load_filters(conn, timeframe):
    """
    Exact filter fields used by analyze_filters_grid.py:

        strategy_scores.market_context_score >= 55
        features.atr_pct_14 <= 0.060
    """

    rows = conn.execute("""
        SELECT
            s.market_id,
            s.timestamp,
            s.market_context_score,
            f.atr_pct_14
        FROM strategy_scores s
        JOIN features f
          ON f.market_id = s.market_id
         AND f.timeframe = s.timeframe
         AND f.timestamp = s.timestamp
        WHERE s.timeframe=?
    """, (timeframe,)).fetchall()

    result = {}

    for market_id, ts, market_context_score, atr_pct_14 in rows:
        if (
            market_context_score is None
            or atr_pct_14 is None
        ):
            continue

        result[(market_id, ts)] = (
            float(market_context_score),
            float(atr_pct_14),
        )

    return result

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


def run_variant(timeframe, filtered, mc_min=55.0, atr_max=0.060):
    conn = sqlite3.connect(DB_PATH)

    markets, bars = load_data(conn, timeframe)
    signals = load_signals(conn, timeframe)
    filters = load_filters(conn, timeframe)

    conn.close()

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

    timestamps = sorted({
        ts
        for series in bars.values()
        for ts, *_ in series
    })

    cash = INITIAL_CAPITAL
    positions = []
    trades = []
    equity_curve = []

    total_fees = 0.0
    total_turnover = 0.0
    total_slippage = 0.0

    for current_ts in timestamps:

        # =====================================================
        # 1. Manage existing positions
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

            # STOP
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

            # TARGET 1
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

            # TARGET 2
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

            # TIME EXIT
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

                # ------------------------------------------------
                # FILTER
                # ------------------------------------------------

                if filtered:

                    filt = filters.get(
                        (market_id, current_ts)
                    )

                    if filt is None:
                        continue

                    market_context, atr_pct = filt

                    if market_context < mc_min:
                        continue

                    if atr_pct > atr_max:
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

    # =========================================================
    # 4. Force close
    # =========================================================

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

    # =========================================================
    # 5. Metrics
    # =========================================================

    final_equity = cash

    total_return = (
        final_equity / INITIAL_CAPITAL - 1
    ) * 100

    peak = INITIAL_CAPITAL
    max_drawdown = 0.0
    max_dd_time = None

    for ts, equity in equity_curve:

        if equity > peak:
            peak = equity

        drawdown = (
            equity / peak - 1
        ) * 100

        if drawdown < max_drawdown:
            max_drawdown = drawdown
            max_dd_time = ts

    wins = [
        t for t in trades
        if t["pnl"] > 0
    ]

    losses = [
        t for t in trades
        if t["pnl"] < 0
    ]

    gross_profit = sum(
        t["pnl"] for t in wins
    )

    gross_loss = abs(sum(
        t["pnl"] for t in losses
    ))

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    win_rate = (
        len(wins) / len(trades) * 100
        if trades
        else 0
    )

    average_trade = (
        sum(t["pnl"] for t in trades) / len(trades)
        if trades
        else 0
    )

    return {
        "final_equity": final_equity,
        "return_pct": total_return,
        "max_drawdown_pct": max_drawdown,
        "max_dd_time": max_dd_time,
        "trade_count": len(trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "average_trade": average_trade,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_fees": total_fees,
        "total_turnover": total_turnover,
        "total_slippage": total_slippage,
        "trades": trades,
        "equity_curve": equity_curve,
    }


def print_result(name, result):
    print(f"\n===== {name} =====")
    print(f"Final Equity       : {result['final_equity']:,.2f}")
    print(f"Return             : {result['return_pct']:+.2f}%")
    print(f"Max Drawdown       : {result['max_drawdown_pct']:.2f}%")
    print(f"Trades             : {result['trade_count']}")
    print(f"Win Rate           : {result['win_rate']:.2f}%")
    print(
        f"Profit Factor      : "
        f"{result['profit_factor']:.3f}"
        if result["profit_factor"] is not None
        else "Profit Factor      : N/A"
    )
    print(f"Average Trade      : {result['average_trade']:,.2f}")
    print(f"Gross Profit       : {result['gross_profit']:,.2f}")
    print(f"Gross Loss         : {result['gross_loss']:,.2f}")
    print(f"Fees               : {result['total_fees']:,.2f}")
    print(f"Slippage           : {result['total_slippage']:,.2f}")
    print(f"Turnover           : {result['total_turnover']:,.2f}")


def main():
    timeframe = "1D"

    print("Running independent backtests...")
    print("FILTER: Market Context >= 55 AND ATR% <= 0.060")

    baseline = run_variant(
        timeframe,
        filtered=False,
    )

    filtered = run_variant(
        timeframe,
        filtered=True,
    )

    print_result(
        "BASELINE",
        baseline,
    )

    print_result(
        "FILTERED",
        filtered,
    )

    print("\n===== COMPARISON =====")

    print(
        f"Final Equity Difference : "
        f"{filtered['final_equity'] - baseline['final_equity']:+,.2f}"
    )

    print(
        f"Return Difference       : "
        f"{filtered['return_pct'] - baseline['return_pct']:+.2f} pp"
    )

    print(
        f"Max DD Difference       : "
        f"{filtered['max_drawdown_pct'] - baseline['max_drawdown_pct']:+.2f} pp"
    )

    print(
        f"Trade Count Difference  : "
        f"{filtered['trade_count'] - baseline['trade_count']:+d}"
    )

    print(
        f"Win Rate Difference     : "
        f"{filtered['win_rate'] - baseline['win_rate']:+.2f} pp"
    )

    if (
        baseline["profit_factor"] is not None
        and filtered["profit_factor"] is not None
    ):
        print(
            f"Profit Factor Difference: "
            f"{filtered['profit_factor'] - baseline['profit_factor']:+.3f}"
        )

    print("\n===== MAX DD DETAILS =====")
    print(
        f"Baseline DD : "
        f"{baseline['max_drawdown_pct']:.2f}% "
        f"at timestamp {baseline['max_dd_time']}"
    )
    print(
        f"Filtered DD : "
        f"{filtered['max_drawdown_pct']:.2f}% "
        f"at timestamp {filtered['max_dd_time']}"
    )


if __name__ == "__main__":
    main()
