import os
import json
import uuid
from fastapi import APIRouter, HTTPException, Body, Query, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.sql import text

from data_sync import engine, orders_table, openai_client

# Haystack imports
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret

router = APIRouter()
security = HTTPBearer() # This forces the route to expect an Authorization header

LITELLM_BASE_URL = os.environ["LITELLM_BASE_URL"]

# --- Tool Implementations ---
async def check_stock(product_id: int):
    print(f"Checking stock for product ID: {product_id}")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT stock_quantity FROM products WHERE id = :id"),
            {"id": product_id}
        )
        row = result.fetchone()
        if row:
            return {"product_id": product_id, "stock": row[0]}
    return {"product_id": product_id, "error": "Product not found"}

async def create_order(product_id: int, quantity: int, customer_phone: str, address: str):
    print(f"Creating order for product ID: {product_id}, quantity: {quantity}")
    order_id = f"ORD{uuid.uuid4().hex[:8].upper()}"
    try:
        async with engine.begin() as conn:
            await conn.execute(
                orders_table.insert().values(
                    id=order_id,
                    product_id=product_id,
                    quantity=quantity,
                    customer_phone=customer_phone,
                    address=address,
                    status='pending'
                )
            )
        return {"order_id": order_id, "status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Tool Definitions ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Checks the stock for a given product ID.",
            "parameters": {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Creates an order for a given product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "quantity": {"type": "integer"},
                    "customer_phone": {"type": "string"},
                    "address": {"type": "string"}
                },
                "required": ["product_id", "quantity", "customer_phone", "address"]
            }
        }
    }
]

# Simple in-memory storage for conversations
conversation_memory = {}

class ChatRequest(BaseModel):
    query: str
    conversation_id: str | None = None

@router.post("/chat")
async def chat(
    request: ChatRequest | None = Body(default=None),
    query: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials = Depends(security) # <--- REQUIRES CUSTOMER KEY
):
    try:
        # 1. Grab the Customer's specific API Key from the request
        customer_api_key = credentials.credentials
        
        # 2. Instantiate Haystack specifically for THIS customer's key, NOT the master key!
        llm = OpenAIChatGenerator(
            api_key=Secret.from_token(customer_api_key),
            api_base_url=LITELLM_BASE_URL,
            model="qwen"
        )
        
        final_query = request.query if request else query
        conv_id = (request.conversation_id if request else None) or str(uuid.uuid4())
        
        if not final_query:
            raise HTTPException(status_code=422, detail="Query is required.")

        # 3. RAG Retrieval Step (Fetch embeddings and search DB)
        embed_response = await openai_client.embeddings.create(input=final_query, model="embeddings")
        vector = embed_response.data[0].embedding
        
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT id, title, stock_quantity FROM products ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT 5"),
                {"embedding": vector}
            )
            rows = result.fetchall()
            retrieved_docs = "\n".join([f"ID: {row[0]}, Title: {row[1]}, Stock: {row[2]}" for row in rows])

        # 4. Setup System Prompt & Memory
        system_prompt = (
            "You are an e-commerce assistant. "
            "Always refer to the user's conversation history to remember product IDs. "
            f"Here are products related to the latest query:\n{retrieved_docs}"
        )

        if conv_id not in conversation_memory:
            conversation_memory[conv_id] = [ChatMessage.from_system(system_prompt)]
        else:
            conversation_memory[conv_id][0] = ChatMessage.from_system(system_prompt)
            
        # Add user query
        conversation_memory[conv_id].append(ChatMessage.from_user(final_query))

        # 5. Call Haystack LLM (LiteLLM bills THIS customer's key)
        response = llm.run(messages=conversation_memory[conv_id], tools=tools)
        reply = response["replies"][0]

        # 6. Handle Tool Calls gracefully
        if reply.tool_calls:
            conversation_memory[conv_id].append(reply)
            
            for call in reply.tool_calls:
                if call.tool_name == "check_stock":
                    res = await check_stock(**call.arguments)
                    conversation_memory[conv_id].append(ChatMessage.from_tool(json.dumps(res), origin=call))
                elif call.tool_name == "create_order":
                    res = await create_order(**call.arguments)
                    conversation_memory[conv_id].append(ChatMessage.from_tool(json.dumps(res), origin=call))
            
            # Get final response after tool execution
            final_response = llm.run(messages=conversation_memory[conv_id], tools=tools)
            final_reply = final_response["replies"][0]
            conversation_memory[conv_id].append(final_reply)
            
            return {"response": final_reply.content, "conversation_id": conv_id}
            
        # 7. Normal chat response
        conversation_memory[conv_id].append(reply)
        return {"response": reply.content, "conversation_id": conv_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
