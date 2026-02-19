import os
import json
import operator
from typing import TypedDict, Annotated, List
import uuid

from fastapi import APIRouter, HTTPException, Body, Query
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from sqlalchemy.sql import text
from langchain_experimental.llms.ollama_functions import OllamaFunctions
from langchain_core.tools import Tool

from data_sync import engine, embeddings

router = APIRouter()

# --- Configurations ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
LLM_MODEL = "qwen"

# Use the OllamaFunctions wrapper for tool-calling
llm = OllamaFunctions(model=LLM_MODEL, format="json", base_url=OLLAMA_BASE_URL)

# --- Tool Definitions ---

def check_stock(product_id: int):
    """Checks the stock for a given product ID."""
    print(f"Checking stock for product ID: {product_id}")
    return {"product_id": product_id, "stock": 100}

def create_order(product_id: int, quantity: int, customer_phone: str, address: str):
    """Creates an order for a given product."""
    print(f"Creating order for product ID: {product_id}, quantity: {quantity}, customer: {customer_phone}, address: {address}")
    return {"order_id": f"ORD{uuid.uuid4().hex[:8].upper()}", "status": "success"}

tool_map = {
    "check_stock": check_stock,
    "create_order": create_order,
}

# Pydantic models for tool schemas
class CheckStock(BaseModel):
    product_id: int = Field(description="The ID of the product to check.")

class CreateOrder(BaseModel):
    product_id: int = Field(description="The ID of the product to order.")
    quantity: int = Field(description="The number of items to order.")
    customer_phone: str = Field(description="The customer's phone number.")
    address: str = Field(description="The shipping address for the order.")

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools=[CheckStock, CreateOrder])

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- LangGraph Nodes ---

async def retrieve(state):
    """Retrieve relevant documents from the database."""
    print("---RETRIEVE NODE---")
    last_message = state['messages'][-1]
    
    query_embedding = await embeddings.aembed_query(last_message.content)

    print(f"Query embedding generated for: {last_message.content}")

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT title, description FROM products ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT 3"),
            {"embedding": query_embedding}
        )
        retrieved_docs = "\n".join([f"Title: {row[0]}\nDescription: {row[1]}" for row in result.fetchall()])
    
    if retrieved_docs:
        print(f"Retrieved context:\n{retrieved_docs}")
        return {"messages": [SystemMessage(content=f"Retrieved context:\n{retrieved_docs}")]}
    return {}

async def agent(state):
    """Invoke the LLM with the current state to decide on an action."""
    print("---AGENT NODE---")
    system_message = "You are an e-commerce assistant. Use the available tools to answer questions and fulfill user requests."
    messages_for_llm = [SystemMessage(content=system_message)] + state["messages"]
    response = await llm_with_tools.ainvoke(messages_for_llm)
    
    print("LLM Response:", response)
    print("Tool calls:", getattr(response, "tool_calls", None))
    
    return {"messages": [response]}

async def tool_executor(state):
    """Execute tools and return the results."""
    print("---TOOL EXECUTOR NODE---")
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    
    responses = []
    for call in tool_calls:
        tool_name = call['name']
        if tool_name in tool_map:
            tool_function = tool_map[tool_name]
            tool_args = call['args']
            try:
                result = tool_function(**tool_args)
                responses.append(
                    ToolMessage(content=json.dumps(result), tool_call_id=call['id'])
                )
            except Exception as e:
                responses.append(
                    ToolMessage(content=f"Error executing tool {tool_name}: {e}", tool_call_id=call['id'])
                )
        else:
            responses.append(
                ToolMessage(content=f"Tool '{tool_name}' not found.", tool_call_id=call['id'])
            )
            
    return {"messages": responses}

def should_continue(state):
    """Decide whether to continue the agent loop or end."""
    if state['messages'][-1].tool_calls:
        return "tools"
    return "end"

# --- Graph Definition ---
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("agent", agent)
workflow.add_node("tools", tool_executor)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
workflow.add_edge("tools", "agent")

# --- Add Memory to Graph ---
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
