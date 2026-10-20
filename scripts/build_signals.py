from app.signals.engine import build_signals


def main():
    total = 0

    for timeframe in ("1D", "4h"):
        print(f"Building signals: {timeframe}", flush=True)

        count = build_signals(timeframe)

        print(
            f"{timeframe}: {count:,} signals",
            flush=True,
        )

        total += count

    print("=" * 80)
    print("SIGNAL ENGINE COMPLETE")
    print(f"Total signal rows: {total:,}")
    print("=" * 80)


if __name__ == "__main__":
    main()
