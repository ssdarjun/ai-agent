from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from data_sync import sync_data, create_table, get_data, get_orders
from chat import router as chat_router

# --- FastAPI App Initialization ---
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await create_table()

# --- CORS Middleware ---
# This is to allow the frontend to make requests to the backend.
# For production, it's better to restrict the origins to the frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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

@app.get("/orders")
async def orders():
    orders_data = await get_orders()
    return {"orders": orders_data}

@app.get("/")
async def read_root():
    return {"message": "AI Agent is running"}
