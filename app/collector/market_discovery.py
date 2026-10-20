from app.db.database import connect
from app.exchanges.bitpin import BitpinClient


def discover_usdt_markets():
    rows = BitpinClient().markets()

    discovered = []

    with connect() as conn:
        for row in rows:
            base = str(row.get("base") or "").upper()
            quote = str(row.get("quote") or "").upper()
            symbol = str(row.get("symbol") or "").upper()

            if quote != "USDT":
                continue

            if not base or not symbol:
                continue

            tradable = bool(row.get("tradable"))
            suspended = bool(row.get("suspended"))

            conn.execute(
                """
                INSERT INTO markets (
                    exchange,
                    exchange_market_id,
                    symbol,
                    base_symbol,
                    quote_symbol,
                    status,
                    tradable,
                    suspended,
                    otc_tradable,
                    coming_soon,
                    price,
                    volume_24h,
                    price_increment,
                    price_precision,
                    quantity_precision
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(exchange, exchange_market_id)
                DO UPDATE SET
                    symbol = excluded.symbol,
                    base_symbol = excluded.base_symbol,
                    quote_symbol = excluded.quote_symbol,
                    status = excluded.status,
                    tradable = excluded.tradable,
                    suspended = excluded.suspended,
                    otc_tradable = excluded.otc_tradable,
                    coming_soon = excluded.coming_soon,
                    price_precision = excluded.price_precision,
                    quantity_precision = excluded.quantity_precision,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    "bitpin",
                    symbol,
                    symbol,
                    base,
                    quote,
                    "active" if tradable and not suspended else "inactive",
                    int(tradable),
                    int(suspended),
                    0,
                    0,
                    None,
                    None,
                    None,
                    (
                        int(row["price_precision"])
                        if row.get("price_precision") is not None
                        else None
                    ),
                    (
                        int(row["base_amount_precision"])
                        if row.get("base_amount_precision") is not None
                        else None
                    ),
                ),
            )

            discovered.append({
                "symbol": symbol,
                "base": base,
                "quote": quote,
                "tradable": tradable,
                "suspended": suspended,
                "price_precision": row.get("price_precision"),
                "base_amount_precision": row.get(
                    "base_amount_precision"
                ),
            })

        conn.commit()

    return discovered
