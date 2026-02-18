import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from sqlalchemy import Table, Column, MetaData, Integer, Text, Float, event
from pgvector.sqlalchemy import Vector
from pgvector.psycopg import register_vector_async
from sqlalchemy.dialects.postgresql import insert as pg_insert
from langchain_ollama import OllamaEmbeddings
import asyncio

# --- Database and API Configuration ---
DB_USER = os.environ.get("POSTGRES_USER", "user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password")
DB_HOST = "pgvector"
DB_NAME = os.environ.get("POSTGRES_DB", "vectordb")
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

API_URL = os.environ.get("API_URL")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")

engine = create_async_engine(DATABASE_URL)

# --- Register Vector Type with Psycopg ---
@event.listens_for(engine.sync_engine, "connect")
def _sqla_on_connect(dbapi_connection, connection_record):
    dbapi_connection.run_async(register_vector_async)

embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)

# --- SQLAlchemy Table Definition ---
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
    Column('embedding', Vector(768))
)

async def create_table():
    """Creates the 'products' table with a vector column if it doesn't exist."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(metadata.create_all, checkfirst=True)

async def sync_data():
    """Fetches data from the API, generates embeddings, and upserts into the database."""
    async with httpx.AsyncClient() as client:
        response = await client.get(API_URL)
        response.raise_for_status()
        products = response.json()

    async with engine.begin() as conn:
        for product in products:
            content_to_embed = f"{product['title']}: {product['description']}"
            vector = await embeddings.aembed_query(content_to_embed)

            stmt = pg_insert(products_table).values(
                id=product['id'],
                title=product['title'],
                price=product['price'],
                description=product['description'],
                category=product['category'],
                image=product['image'],
                embedding=vector # Pass the list directly
            )
            
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'title': stmt.excluded.title,
                    'price': stmt.excluded.price,
                    'description': stmt.excluded.description,
                    'category': stmt.excluded.category,
                    'image': stmt.excluded.image,
                    'embedding': stmt.excluded.embedding,
                }
            )
            await conn.execute(upsert_stmt)
            
    print("Data synchronization complete.")

async def get_data():
    """Retrieves all data from the 'products' table."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, title, price, description, category, image FROM products"))
        products = result.fetchall()
        return [dict(zip(result.keys(), product)) for product in products]
    print("Data retrieval complete.")


if __name__ == "__main__":
    async def main():
        await create_table()
        await sync_data()
        await get_data()
    asyncio.run(main())
