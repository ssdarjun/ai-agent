import os
import httpx
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text
from sqlalchemy import event
from fastapi import FastAPI, HTTPException
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List, Union
import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from pydantic import BaseModel, Field
import json
from pgvector.psycopg import register_vector_async
from langchain_ollama import OllamaLLM, OllamaEmbeddings

from data_sync import sync_data, create_table

# --- FastAPI App Initialization ---
app = FastAPI()

# --- Configurations ---
DB_USER = os.environ.get("POSTGRES_USER", "user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "password")
DB_HOST = "pgvector"
DB_NAME = os.environ.get("POSTGRES_DB", "vectordb")
DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
LLM_MODEL = "qwen"
EMBEDDING_MODEL = "nomic-embed-text"

# --- Database, LLM, and Embeddings ---
engine = create_async_engine(DATABASE_URL)

# --- Register Vector Type with Psycopg ---
@event.listens_for(engine.sync_engine, "connect")
def _sqla_on_connect(dbapi_connection, connection_record):
    dbapi_connection.run_async(register_vector_async)

llm = OllamaLLM(model=LLM_MODEL, base_url=OLLAMA_BASE_URL)
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


# --- Agent Tools ---
def check_stock(product_id: int):
    """Checks the stock for a given product ID."""
    return {"product_id": product_id, "stock": 100}

def create_order(product_id: int, quantity: int, customer_phone: str, address: str):
    """Creates an order for a given product."""
    return {"order_id": "ORD12345", "status": "success"}

tools = {
    "check_stock": check_stock,
    "create_order": create_order,
}

# --- Pydantic Models for Agent Output ---
class ToolCall(BaseModel):
    tool: str = Field(description="The name of the tool to use.")
    tool_input: dict = Field(description="The input for the tool.")

class NaturalResponse(BaseModel):
    response: str = Field(description="The natural language response to the user.")

class AgentOutput(BaseModel):
    output: Union[ToolCall, NaturalResponse]

parser = PydanticOutputParser(pydantic_object=AgentOutput)

# --- Agent State ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# --- LangGraph Nodes ---
async def retrieve(state):
    """Retrieve relevant documents from the database."""
    last_message = state['messages'][-1]
    
    query_embedding = await embeddings.aembed_query(last_message.content)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT title, description FROM products ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT 5"),
            {"embedding": query_embedding} # Pass the list directly
        )
        retrieved_docs = "\n".join([f"Title: {row[0]}\nDescription: {row[1]}" for row in result.fetchall()])
    
    return {"messages": [SystemMessage(content=f"Retrieved context:\n{retrieved_docs}")]}


async def agent(state):
    """The main agent logic."""
    prompt = PromptTemplate(
        template="""You are an e-commerce assistant. Based on the retrieved context, answer the user's question or decide to use a tool.

        {format_instructions}
        
        Available tools:
        - check_stock(product_id: int)
        - create_order(product_id: int, quantity: int, customer_phone: str, address: str)
        
        User question: {question}
        Context: {context}
        """,
        input_variables=["question", "context"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )
    
    chain = prompt | llm | parser
    
    context = "\n".join([msg.content for msg in state["messages"] if isinstance(msg, (SystemMessage, ToolMessage))])
    question = state["messages"][-1].content
    
    response = await chain.ainvoke({"question": question, "context": context})
    
    return {"messages": [AIMessage(content=json.dumps(response.dict()))]}


async def tool_executor(state):
    """Executes the tool call."""
    tool_call_dict = json.loads(state['messages'][-1].content)
    tool_call = ToolCall(**tool_call_dict['output'])
    
    tool_name = tool_call.tool
    tool_input = tool_call.tool_input

    if tool_name in tools:
        result = tools[tool_name](**tool_input)
        return {"messages": [ToolMessage(content=json.dumps(result))]}
    else:
        return {"messages": [ToolMessage(content="Tool not found")]}


def should_continue(state):
    """Determines whether to continue the graph."""
    last_message = state['messages'][-1]
    if isinstance(last_message, AIMessage):
        try:
            content = json.loads(last_message.content)
            if 'output' in content and 'tool' in content['output']:
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
async def trigger_sync():
    """Triggers the data synchronization process."""
    try:
        await create_table()
        await sync_data()
        return {"message": "Data synchronization started."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(query: str):
    """Handles user queries and interacts with the agent."""
    try:
        inputs = {"messages": [HumanMessage(content=query)]}
        result = await app_graph.ainvoke(inputs)
        final_content = result['messages'][-1].content
        
        # The final content is a JSON string from either AIMessage or ToolMessage
        # We need to parse it to get the actual response.
        parsed_content = json.loads(final_content)

        if 'output' in parsed_content and 'response' in parsed_content['output']:
            return {"response": parsed_content['output']['response']}
        else:
            return {"response": parsed_content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def read_root():
    return {"message": "AI Agent is running"}
