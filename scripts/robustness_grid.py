from __future__ import annotations

from scripts.compare_baseline_filtered import run_variant

TIMEFRAME = "1D"

MC_VALUES = (50.0, 55.0, 60.0)
ATR_VALUES = (0.050, 0.060, 0.070)


def main():
    print("Running robustness grid...")
    print()

    rows = []

    for mc in MC_VALUES:
        for atr in ATR_VALUES:
            print(
                f"Testing MC >= {mc:.0f}, "
                f"ATR <= {atr:.3f} ..."
            )

            r = run_variant(
                TIMEFRAME,
                filtered=True,
                mc_min=mc,
                atr_max=atr,
            )

            rows.append({
                "mc": mc,
                "atr": atr,
                "trades": r["trade_count"],
                "pnl": r["final_equity"] - 100_000_000,
                "return": r["return_pct"],
                "dd": r["max_drawdown_pct"],
                "win": r["win_rate"],
                "pf": r["profit_factor"],
            })

    print()
    print("=" * 100)
    print("ROBUSTNESS GRID")
    print("=" * 100)

    print(
        f"{'MC':>6}"
        f"{'ATR':>8}"
        f"{'Trades':>9}"
        f"{'PnL':>18}"
        f"{'Return':>11}"
        f"{'MaxDD':>11}"
        f"{'Win%':>10}"
        f"{'PF':>9}"
    )

    print("-" * 100)

    for r in rows:
        pf = (
            f"{r['pf']:.3f}"
            if r["pf"] is not None
            else "-"
        )

        print(
            f"{r['mc']:>6.0f}"
            f"{r['atr']*100:>7.1f}%"
            f"{r['trades']:>9}"
            f"{r['pnl']:>18,.2f}"
            f"{r['return']:>10.2f}%"
            f"{r['dd']:>10.2f}%"
            f"{r['win']:>9.2f}%"
            f"{pf:>9}"
        )


if __name__ == "__main__":
    main()
