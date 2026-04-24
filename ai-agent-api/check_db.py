import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from app.data_sync import engine
from sqlalchemy import text

async def check():
    try:
        async with engine.connect() as conn:
            # Check if orders table exists
            query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'orders')")
            res = await conn.execute(query)
            exists = res.scalar()
            print(f"Orders table exists: {exists}")
            
            if exists:
                query_cols = text("SELECT column_name FROM information_schema.columns WHERE table_name = 'orders'")
                res_cols = await conn.execute(query_cols)
                print(f"Columns: {[r[0] for r in res_cols.fetchall()]}")
            else:
                print("Orders table is MISSING!")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
