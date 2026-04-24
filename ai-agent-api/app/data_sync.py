import os
import httpx
import random
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from sqlalchemy import Table, Column, MetaData, Integer, Text, Float, event
from pgvector.sqlalchemy import Vector
from pgvector.psycopg import register_vector_async
from sqlalchemy.dialects.postgresql import insert as pg_insert
from openai import AsyncOpenAI

# --- Configuration ---
DATABASE_URL = os.environ["DATABASE_URL"]
API_URL = os.environ["API_URL"]
LITELLM_BASE_URL = os.environ["LITELLM_BASE_URL"]
LITELLM_MASTER_KEY = os.environ["LITELLM_MASTER_KEY"]

# --- Database & OpenAI Clients ---
engine = create_async_engine(DATABASE_URL)
openai_client = AsyncOpenAI(api_key=LITELLM_MASTER_KEY, base_url=LITELLM_BASE_URL)

@event.listens_for(engine.sync_engine, "connect")
def _sqla_on_connect(dbapi_connection, connection_record):
    try:
        dbapi_connection.run_async(register_vector_async)
    except Exception:
        # Ignore error if vector extension is not yet installed
        # It will be registered on subsequent connections after create_table() runs
        pass

# --- Schema ---
metadata = MetaData()
products_table = Table(
    'products',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=False),
    Column('title', Text),
    Column('price', Float),
    Column('description', Text),
    Column('category', Text),
    Column('image', Text),
    Column('stock_quantity', Integer, default=0),
    Column('embedding', Vector(768))
)

orders_table = Table(
    'orders',
    metadata,
    Column('id', Text, primary_key=True),
    Column('product_id', Integer),
    Column('quantity', Integer),
    Column('customer_phone', Text),
    Column('address', Text),
    Column('status', Text, default='pending'),
    Column('created_at', Text, server_default=text("CURRENT_TIMESTAMP"))
)

async def create_table():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(metadata.create_all, checkfirst=True)
        
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='products' AND column_name='stock_quantity'"
        ))
        if not result.fetchone():
            await conn.execute(text("ALTER TABLE products ADD COLUMN stock_quantity INTEGER DEFAULT 0"))

async def sync_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL)
        response.raise_for_status()
        products = response.json()

    async with engine.begin() as conn:
        for product in products:
            content_to_embed = f"{product['title']}: {product['description']}"
            
            # Fast, async call to LiteLLM for embedding!
            embed_response = await openai_client.embeddings.create(input=content_to_embed, model="embeddings")
            vector = embed_response.data[0].embedding
            
            stock = product.get('stock_quantity', random.randint(5, 50))

            stmt = pg_insert(products_table).values(
                id=product['id'],
                title=product['title'],
                price=product['price'],
                description=product['description'],
                category=product['category'],
                image=product['image'],
                stock_quantity=stock,
                embedding=vector
            )
            
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'title': stmt.excluded.title,
                    'price': stmt.excluded.price,
                    'description': stmt.excluded.description,
                    'category': stmt.excluded.category,
                    'image': stmt.excluded.image,
                    'stock_quantity': stmt.excluded.stock_quantity,
                    'embedding': stmt.excluded.embedding,
                }
            )
            await conn.execute(upsert_stmt)
            
    print("Data synchronization complete.")

async def get_data():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, title, price, description, category, image, stock_quantity FROM products"))
        products = result.fetchall()
        return [dict(zip(result.keys(), product)) for product in products]

async def get_orders():
    async with engine.connect() as conn:
        query = text("""
            SELECT o.id, o.product_id, p.title as product_title, o.quantity, o.customer_phone, o.address, o.status, o.created_at
            FROM orders o
            JOIN products p ON o.product_id = p.id
            ORDER BY o.created_at DESC
        """)
        result = await conn.execute(query)
        orders = result.fetchall()
        return [dict(zip(result.keys(), order)) for order in orders]

if __name__ == "__main__":
    async def main():
        await create_table()
        await sync_data()
        await get_data()
    asyncio.run(main())
