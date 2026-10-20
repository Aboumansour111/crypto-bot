from app.analysis.market_context import build_market_context


def main():
    total = 0

    for timeframe in ("1D", "4h"):
        print(f"Building market context: {timeframe}", flush=True)

        count = build_market_context(timeframe)

        print(
            f"{timeframe}: {count:,} context rows",
            flush=True,
        )

        total += count

    print("=" * 80)
    print("MARKET CONTEXT COMPLETE")
    print(f"Total rows: {total:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
