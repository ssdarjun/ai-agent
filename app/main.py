
import os
from fastapi import FastAPI, HTTPException
from langchain_community.llms import Ollama
from langchain_community.embeddings import OllamaEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator
from langchain_core.messages import BaseMessage
from sqlalchemy import create_engine, text
import json

from app.data_sync import sync_data, create_table

# --- FastAPI App Initialization ---
app = FastAPI()

# --- Configurations ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/vectordb")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = "qwen"
EMBEDDING_MODEL = "nomic-embed-text"

# --- Database, LLM, and Embeddings ---
engine = create_engine(DATABASE_URL)
llm = Ollama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL)
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


# --- Agent Tools ---
def check_stock(product_id: int):
    """Checks the stock for a given product ID."""
    # In a real application, this would query a database or an API
    return {"product_id": product_id, "stock": 100}

def create_order(product_id: int, quantity: int, customer_phone: str, address: str):
    """Creates an order for a given product."""
    # In a real application, this would call an order management API
    return {"order_id": "ORD12345", "status": "success"}

tools = {
    "check_stock": check_stock,
    "create_order": create_order,
}

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- LangGraph Nodes ---
def retrieve(state):
    """Retrieve relevant documents from the database."""
    last_message = state['messages'][-1].content
    
    # Generate embedding for the user query
    query_embedding = embeddings.embed_query(last_message)

    # Perform vector search
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT title, description FROM products ORDER BY embedding <=> :embedding LIMIT 5"),
            {"embedding": query_embedding}
        ).fetchall()

    retrieved_docs = "\n".join([f"Title: {row[0]}\nDescription: {row[1]}" for row in result])
    
    return {"messages": [("system", f"Retrieved context:\n{retrieved_docs}")]}


def agent(state):
    """The main agent logic."""
    prompt = PromptTemplate(
        template="""You are an e-commerce assistant. Based on the retrieved context, answer the user's question or decide to use a tool.
        
        Available tools:
        - check_stock(product_id: int)
        - create_order(product_id: int, quantity: int, customer_phone: str, address: str)
        
        User question: {question}
        Context: {context}
        
        To use a tool, output a JSON object with 'tool' and 'tool_input' keys.
        Otherwise, provide a natural language response.
        """,
        input_variables=["question", "context"],
    )
    
    chain = prompt | llm | JsonOutputParser()
    
    context = "\n".join([msg.content for msg in state["messages"] if msg.type == "system"])
    question = state["messages"][-1].content
    
    response = chain.invoke({"question": question, "context": context})
    
    return {"messages": [("ai", json.dumps(response))]}


def tool_executor(state):
    """Executes the tool call."""
    tool_call = json.loads(state['messages'][-1].content)
    tool_name = tool_call.get("tool")
    tool_input = tool_call.get("tool_input")

    if tool_name in tools:
        result = tools[tool_name](**tool_input)
        return {"messages": [("tool", json.dumps(result))]}
    else:
        return {"messages": [("tool", "Tool not found")]}


def should_continue(state):
    """Determines whether to continue the graph."""
    last_message = state['messages'][-1]
    if last_message.type == "ai":
        try:
            content = json.loads(last_message.content)
            if "tool" in content:
                return "tools"
        except (json.JSONDecodeError, TypeError):
            pass
    return "end"
    

# --- Graph Definition ---
workflow = StateGraph(AgentState)
workflow.add_node("retrieve", retrieve)
workflow.add_node("agent", agent)
workflow.add_node("tools", tool_executor)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END,
    },
)
workflow.add_edge("tools", "agent")

app_graph = workflow.compile()

# --- FastAPI Endpoints ---
@app.post("/sync")
def trigger_sync():
    """Triggers the data synchronization process."""
    try:
        create_table()
        sync_data()
        return {"message": "Data synchronization started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(query: str):
    """Handles user queries and interacts with the agent."""
    try:
        inputs = {"messages": [("user", query)]}
        result = app_graph.invoke(inputs)
        return {"response": result['messages'][-1].content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"message": "AI Agent is running"}

