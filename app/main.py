from fastapi import FastAPI, HTTPException
from data_sync import sync_data, create_table, get_data
from chat import router as chat_router

# --- FastAPI App Initialization ---
app = FastAPI()

# --- Include Chat Router ---
app.include_router(chat_router)

# --- FastAPI Endpoints ---
@app.post("/sync")
async def trigger_sync():
    """Triggers the data synchronization process."""
    try:
        await create_table()
        await sync_data()
        return {"message": "Data synchronization started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/products")
async def products():
    products_data = await get_data()
    return {"products": products_data}

@app.get("/")
async def read_root():
    return {"message": "AI Agent is running"}
