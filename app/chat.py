import os
import json
import operator
from typing import TypedDict, Annotated, List, Literal
import uuid

from fastapi import APIRouter, HTTPException, Body, Query
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from sqlalchemy.sql import text

# NEW: Use the standard ChatOllama class
from langchain_ollama import ChatOllama 

from data_sync import engine, embeddings, orders_table

router = APIRouter()

# --- Configurations ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
LLM_MODEL = "qwen2.5:7b" # Ensure you use a tool-calling optimized version

# Initialize with temperature 0 for consistent tool calls
llm = ChatOllama(
    model=LLM_MODEL, 
    base_url=OLLAMA_BASE_URL,
    temperature=0,
)

# --- Tool Definitions ---
class CheckStock(BaseModel):
    product_id: int = Field(description="The ID of the product to check.")

class CreateOrder(BaseModel):
    product_id: int = Field(description="The ID of the product to order.")
    quantity: int = Field(description="The number of items to order.")
    customer_phone: str = Field(description="The customer's phone number.")
    address: str = Field(description="The shipping address for the order.")

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools=[CheckStock, CreateOrder])

async def check_stock(product_id: int):
    """Checks the stock for a given product ID by querying the database."""
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
    """Creates an order for a given product and stores it in the database."""
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
        return {"order_id": order_id, "status": "success", "message": "Order created successfully"}
    except Exception as e:
        print(f"Error creating order: {e}")
        return {"status": "error", "message": str(e)}

tool_map = {
    "CheckStock": check_stock,
    "CreateOrder": create_order,
}

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- LangGraph Nodes ---

async def retrieve(state):
    """Retrieve relevant documents from the database including IDs and stock."""
    print("---RETRIEVE NODE---")
    last_message = state['messages'][-1]
    if not isinstance(last_message, HumanMessage):
        return {}
    
    query_embedding = await embeddings.aembed_query(last_message.content)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT id, title, description, stock_quantity FROM products ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT 20"),
            {"embedding": query_embedding}
        )
        rows = result.fetchall()
        if not rows:
            return {}
        retrieved_docs = "\n".join([f"ID: {row[0]}, Title: {row[1]}, Stock: {row[3]}, Description: {row[2][:100]}..." for row in rows])
    
    return {"messages": [SystemMessage(content=f"Available products in this context:\n{retrieved_docs}")]}

async def agent(state):
    """Invoke the LLM with the current state."""
    print("---AGENT NODE---")
    system_prompt = (
        "You are a professional e-commerce assistant for MyStore. "
        "Your goal is to help users check stock and place orders efficiently. "
        "\n\nGUIDELINES:"
        "\n1. MEMORY: Always refer to previous messages to remember which product the user is interested in. "
        "If the user says 'place an order' or 'buy it' after you just checked stock for a product, use that product's ID automatically. "
        "\n2. PRODUCT IDs: Always use numeric IDs for tools. Resolve names to IDs using the provided context. "
        "\n3. CLARITY: If the user hasn't specified quantity, phone, or address for an order, ask for them politely. "
        "\n4. CONTEXT: Use the 'Available products' context to find details, but prioritize what was discussed in history."
    )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}

async def tool_executor(state):
    """Execute tools using the native tool_calls attribute."""
    print("---TOOL EXECUTOR NODE---")
    last_message = state['messages'][-1]
    
    responses = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]
        
        func = tool_map.get(tool_name)
        if func:
            result = await func(**args)
            responses.append(ToolMessage(
                content=json.dumps(result), 
                tool_call_id=tool_call["id"]
            ))
        else:
            responses.append(ToolMessage(
                content=f"Tool {tool_name} not found.", 
                tool_call_id=tool_call["id"]
            ))
            
    return {"messages": responses}

def should_continue(state) -> Literal["tools", "end"]:
    """Decide whether to continue or end."""
    last_message = state['messages'][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

# --- Graph Assembly ---
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("agent", agent)
workflow.add_node("tools", tool_executor)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
workflow.add_edge("tools", "agent")

memory = MemorySaver()
app_graph_with_memory = workflow.compile(checkpointer=memory)

# --- API Models ---
class ChatRequest(BaseModel):
    query: str
    conversation_id: str | None = None

# --- FastAPI Endpoint ---
@router.post("/chat")
async def chat(
    request: ChatRequest | None = Body(default=None),
    query: str | None = Query(default=None, description="Query for backward compatibility.")
):
    """Handles user queries with conversation history."""
    try:
        final_query: str | None = None
        conv_id: str | None = None

        if request:
            final_query = request.query
            conv_id = request.conversation_id
        
        if query:
            final_query = query
            if not request:
                conv_id = None

        if not final_query:
            raise HTTPException(status_code=422, detail="Query is required.")

        conversation_id = conv_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": conversation_id}}
        
        inputs = {"messages": [HumanMessage(content=final_query)]}
        
        final_state = await app_graph_with_memory.ainvoke(inputs, config=config)
        last_message = final_state['messages'][-1]
        
        return {"response": last_message.content, "conversation_id": conversation_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")
