
import os
import requests
from sqlalchemy import create_engine, text
from pgvector.sqlalchemy import Vector
from langchain_community.embeddings import OllamaEmbeddings

# --- Database and API Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/vectordb")
API_URL = os.environ.get("API_URL", "https://fakestoreapi.com/products")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

engine = create_engine(DATABASE_URL)
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)

def create_table():
    """Creates the 'products' table with a vector column if it doesn't exist."""
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                title TEXT,
                price FLOAT,
                description TEXT,
                category TEXT,
                image TEXT,
                embedding VECTOR(768)
            )
        """))
        connection.commit()

def sync_data():
    """Fetches data from the API, generates embeddings, and upserts into the database."""
    response = requests.get(API_URL)
    products = response.json()

    with engine.connect() as connection:
        for product in products:
            # Combine title and description for a richer embedding
            content_to_embed = f"{product['title']}: {product['description']}"
            
            # Generate embedding
            vector = embeddings.embed_query(content_to_embed)

            # Upsert logic (simple version: delete and insert)
            # A more robust solution would use ON CONFLICT DO UPDATE
            connection.execute(text("DELETE FROM products WHERE id = :id"), {"id": product['id']})
            connection.execute(
                text("""
                    INSERT INTO products (id, title, price, description, category, image, embedding)
                    VALUES (:id, :title, :price, :description, :category, :image, :embedding)
                """),
                {
                    "id": product['id'],
                    "title": product['title'],
                    "price": product['price'],
                    "description": product['description'],
                    "category": product['category'],
                    "image": product['image'],
                    "embedding": vector,
                }
            )
        connection.commit()
    print("Data synchronization complete.")

if __name__ == "__main__":
    create_table()
    sync_data()
