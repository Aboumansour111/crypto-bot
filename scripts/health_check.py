from app.db.database import init_db, connect

init_db()

with connect() as conn:
    total = conn.execute(
        "SELECT COUNT(*) FROM markets"
    ).fetchone()[0]

    usdt = conn.execute(
        "SELECT COUNT(*) FROM markets WHERE quote_symbol='USDT'"
    ).fetchone()[0]

    researchable = conn.execute(
        """
        SELECT COUNT(*)
        FROM markets
        WHERE quote_symbol='USDT'
          AND tradable=1
          AND suspended=0
          AND coming_soon=0
        """
    ).fetchone()[0]

print("Crypto Bot Health Check")
print("-" * 40)
print("Database: OK")
print("Markets:", total)
print("USDT markets:", usdt)
print("Researchable USDT:", researchable)
print("Status: OK")
