from app.backtest.engine import run_backtest


def main():

    for timeframe in ("1D", "4h"):

        result = run_backtest(timeframe)

        print()
        print("=" * 80)
        print(f"BACKTEST REPORT — {timeframe}")
        print("=" * 80)

        print(
            f"Initial Capital : "
            f"{result['initial_capital']:,.2f}"
        )

        print(
            f"Final Equity    : "
            f"{result['final_equity']:,.2f}"
        )

        print(
            f"Total Return    : "
            f"{result['return_pct']:.2f}%"
        )

        print(
            f"Max Drawdown    : "
            f"{result['max_drawdown_pct']:.2f}%"
        )

        print(
            f"Trades          : "
            f"{result['trade_count']:,}"
        )

        print(
            f"Win Rate        : "
            f"{result['win_rate']:.2f}%"
        )

        pf = result["profit_factor"]

        print(
            f"Profit Factor   : "
            f"{pf:.3f}" if pf is not None
            else "Profit Factor   : N/A"
        )

        print(
            f"Average Trade   : "
            f"{result['average_trade']:,.2f}"
        )

        print(
            f"Gross Profit    : "
            f"{result['gross_profit']:,.2f}"
        )

        print(
            f"Gross Loss      : "
            f"{result['gross_loss']:,.2f}"
        )

        print(
            f"Total Fees      : "
            f"{result['total_fees']:,.2f}"
        )

        print(
            f"Turnover        : "
            f"{result['total_turnover']:,.2f}"
        )

        print()
        print("MONTHLY RETURNS")
        print("-" * 40)

        for month, ret in result["monthly_returns"].items():
            print(
                f"{month}: {ret:+.2f}%"
            )

        print("=" * 80)


if __name__ == "__main__":
    main()
