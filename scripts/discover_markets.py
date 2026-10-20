from app.db.database import init_db
from app.collector.market_discovery import discover_usdt_markets


init_db()

markets = discover_usdt_markets()

print("=" * 70)
print(f"USDT markets discovered: {len(markets)}")
print("=" * 70)

for item in markets[:30]:
    print(
        f'{item["symbol"]:<20} '
        f'base={item["base"]:<10} '
        f'quote={item["quote"]:<6} '
        f'tradable={item["tradable"]} '
        f'suspended={item["suspended"]}'
    )

print("=" * 70)
