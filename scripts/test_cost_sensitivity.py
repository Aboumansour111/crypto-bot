from scripts import compare_baseline_filtered as bt

TIMEFRAME = "1D"

SCENARIOS = [
    ("CURRENT", 0.0010, 0.0005),
    ("MAKER_ASSUMPTION", 0.0030, 0.0005),
    ("TAKER_STRESS", 0.0035, 0.0010),
]


def main():
    original_fee = bt.FEE_RATE
    original_slippage = bt.SLIPPAGE_RATE

    try:
        print("Filtered strategy: Market Context >= 55, ATR% <= 6%")
        print("All scenarios use the same historical data and strategy.")

        for name, fee, slippage in SCENARIOS:
            bt.FEE_RATE = fee
            bt.SLIPPAGE_RATE = slippage

            print(f"\n{'=' * 65}")
            print(
                f"{name}: fee={fee * 100:.3f}% per side, "
                f"slippage={slippage * 100:.3f}% per side"
            )

            result = bt.run_variant(TIMEFRAME, filtered=True)

            print(f"Trades          : {result['trade_count']}")
            print(f"Final equity    : {result['final_equity']:,.2f}")
            print(f"Net PnL         : "
                  f"{result['final_equity'] - bt.INITIAL_CAPITAL:,.2f}")
            print(f"Return          : {result['return_pct']:+.2f}%")
            print(f"Max drawdown    : {result['max_drawdown_pct']:.2f}%")
            print(f"Win rate        : {result['win_rate']:.2f}%")
            print(f"Profit factor   : {result['profit_factor']:.3f}"
                  if result["profit_factor"] is not None
                  else "Profit factor   : N/A")
            print(f"Average trade   : {result['average_trade']:,.2f}")
            print(f"Total fees      : {result['total_fees']:,.2f}")
            print(f"Total slippage  : {result['total_slippage']:,.2f}")

    finally:
        bt.FEE_RATE = original_fee
        bt.SLIPPAGE_RATE = original_slippage


if __name__ == "__main__":
    main()
