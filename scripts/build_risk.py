from app.risk.engine import build_risk


def main():
    total = 0

    for timeframe in ("1D", "4h"):
        print(f"Building risk sizing: {timeframe}", flush=True)

        count = build_risk(timeframe)

        print(
            f"{timeframe}: {count:,} risk rows",
            flush=True,
        )

        total += count

    print("=" * 80)
    print("RISK ENGINE COMPLETE")
    print(f"Total risk rows: {total:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
