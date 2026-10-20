from app.strategy.scoring import build_scores


def main():
    total = 0

    for timeframe in ("1D", "4h"):
        print(f"Building strategy scores: {timeframe}", flush=True)

        count = build_scores(timeframe)

        print(
            f"{timeframe}: {count:,} scores",
            flush=True,
        )

        total += count

    print("=" * 80)
    print("SCORING ENGINE COMPLETE")
    print(f"Total scores: {total:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
