import asyncio
import sys
from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal, check_database_connection


async def main():
    print("Checking database connection...")
    connected = await check_database_connection()
    if not connected:
        print("ERROR: Database connection failed.")
        sys.exit(1)
    
    print("Database connection OK. Checking tables...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        tables = [row[0] for row in result.fetchall()]
        print(f"Found {len(tables)} tables: {tables}")
    
    print("Database check completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
