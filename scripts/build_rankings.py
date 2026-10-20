from app.strategy.ranking import build_rankings


def main():
    total = 0

    for timeframe in ("1D", "4h"):
        print(
            f"Building rankings: {timeframe}",
            flush=True,
        )

        count = build_rankings(timeframe)

        print(
            f"{timeframe}: {count:,} rankings",
            flush=True,
        )

        total += count

    print("=" * 80)
    print("RANKING ENGINE COMPLETE")
    print(f"Total ranking rows: {total:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
