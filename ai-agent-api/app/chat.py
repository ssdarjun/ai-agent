import os
import json
import uuid
import asyncio
import time
import queue as sync_queue
import threading
from fastapi import APIRouter, HTTPException, Body, Query, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.sql import text

from data_sync import engine, orders_table, openai_client
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import Tool
from haystack.utils import Secret

router = APIRouter()
security = HTTPBearer()

LITELLM_BASE_URL = os.environ["LITELLM_BASE_URL"]
QWEN_MODEL_NAME = os.environ.get("QWEN_MODEL_NAME", "qwen")

# Caps token generation length — biggest single speed lever on a local model.
# 512 tokens ≈ ~400 words, plenty for e-commerce answers.
_GEN_KWARGS = {"max_tokens": 512, "temperature": 0.1}


# --- Tool Implementations ---
async def check_stock(product_id: int):
    print(f"Checking stock for product_id={product_id}")
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT stock_quantity FROM products WHERE id = :id"),
            {"id": product_id},
        )
        row = result.fetchone()
        if row:
            return {"product_id": product_id, "stock": row[0]}
    return {"product_id": product_id, "error": "Product not found"}


async def create_order(product_id: int, quantity: int, customer_phone: str, address: str):
    print(f"Creating order: product={product_id}, qty={quantity}")
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
                    status="pending",
                )
            )
        return {"order_id": order_id, "status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --- Tool Definitions ---
def dummy_func(**kwargs):
    pass


tools = [
    Tool(
        name="check_stock",
        description="Checks the current stock quantity for a given product ID.",
        parameters={
            "type": "object",
            "properties": {"product_id": {"type": "integer"}},
            "required": ["product_id"],
        },
        function=dummy_func,
    ),
    Tool(
        name="create_order",
        description="Creates a new order for a product.",
        parameters={
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer"},
                "customer_phone": {"type": "string"},
                "address": {"type": "string"},
            },
            "required": ["product_id", "quantity", "customer_phone", "address"],
        },
        function=dummy_func,
    ),
]

conversation_memory: dict = {}


class ChatRequest(BaseModel):
    query: str
    conversation_id: str | None = None


def _build_llm(api_key: str, streaming_callback=None) -> OpenAIChatGenerator:
    return OpenAIChatGenerator(
        api_key=Secret.from_token(api_key),
        api_base_url=LITELLM_BASE_URL,
        model=QWEN_MODEL_NAME,
        streaming_callback=streaming_callback,
        generation_kwargs=_GEN_KWARGS,
    )


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest | None = Body(default=None),
    query: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    customer_api_key = credentials.credentials
    final_query = request.query if request else query
    conv_id = (request.conversation_id if request else None) or str(uuid.uuid4())

    if not final_query:
        raise HTTPException(status_code=422, detail="Query is required.")

    try:
        # 1. RAG — embed the query and find similar products
        embed_resp = await openai_client.embeddings.create(
            input=final_query, model="embeddings"
        )
        vector = embed_resp.data[0].embedding

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id, title, stock_quantity FROM products "
                    "ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT 5"
                ),
                {"embedding": vector},
            )
            rows = result.fetchall()

        retrieved_docs = "\n".join(
            f"ID: {r[0]}, Title: {r[1]}, Stock: {r[2]}" for r in rows
        )
        system_prompt = (
            "You are a concise e-commerce assistant. "
            "Use conversation history to remember product IDs across turns. "
            f"Relevant products for this query:\n{retrieved_docs}"
        )

        if conv_id not in conversation_memory:
            conversation_memory[conv_id] = [ChatMessage.from_system(system_prompt)]
        else:
            conversation_memory[conv_id][0] = ChatMessage.from_system(system_prompt)

        conversation_memory[conv_id].append(ChatMessage.from_user(final_query))

        # 2. Non-streaming call to detect whether tool use is needed
        llm = _build_llm(customer_api_key)
        resp = await asyncio.to_thread(
            llm.run, messages=conversation_memory[conv_id], tools=tools
        )
        reply = resp["replies"][0]

        # 3. Tool execution loop (up to 3 rounds)
        executed: set = set()
        for i in range(3):
            if not reply.tool_calls:
                break

            conversation_memory[conv_id].append(reply)

            for call in reply.tool_calls:
                call_key = f"{call.tool_name}:{json.dumps(call.arguments, sort_keys=True)}"
                if call_key in executed:
                    conversation_memory[conv_id].append(
                        ChatMessage.from_system("Give your final answer based on results already provided.")
                    )
                    break
                executed.add(call_key)
                print(f"Tool: {call.tool_name}({call.arguments})")

                if call.tool_name == "check_stock":
                    res = await check_stock(**call.arguments)
                    tool_msg = (
                        f"Tool Result: Product ID {res['product_id']} was not found."
                        if "error" in res
                        else f"Tool Result: Product ID {res['product_id']} has {res['stock']} items in stock."
                    )
                elif call.tool_name == "create_order":
                    res = await create_order(**call.arguments)
                    tool_msg = f"Tool Result: {json.dumps(res)}"
                else:
                    tool_msg = f"Tool Result: unknown tool '{call.tool_name}'"

                conversation_memory[conv_id].append(
                    ChatMessage.from_tool(tool_msg, origin=call)
                )

            # On the last allowed iteration, drop tools to force a text response.
            next_tools = tools if i < 2 else None
            resp = await asyncio.to_thread(
                llm.run, messages=conversation_memory[conv_id], tools=next_tools
            )
            reply = resp["replies"][0]

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # 4. Stream the final answer back to the client via Server-Sent Events

    # Fast path: a non-streaming call already produced text (no tools, or tools + text).
    if reply.text:
        conversation_memory[conv_id].append(reply)

        async def send_existing():
            yield _sse({"token": reply.text})
            yield _sse({"done": True, "conversation_id": conv_id})

        return StreamingResponse(send_existing(), media_type="text/event-stream")

    # Slow path: the model returned only tool calls and no text yet.
    # Run one final streaming call so the user sees tokens as they arrive.
    token_q: sync_queue.Queue = sync_queue.Queue()
    holder: list = []

    def on_chunk(chunk):
        if chunk.content:
            token_q.put(chunk.content)

    streaming_llm = _build_llm(customer_api_key, streaming_callback=on_chunk)

    def run_stream():
        try:
            result = streaming_llm.run(messages=conversation_memory[conv_id])
            holder.append(result["replies"][0])
        except Exception as exc:
            print(f"Streaming LLM error: {exc}")
            holder.append(None)
        finally:
            token_q.put(None)  # sentinel

    llm_thread = threading.Thread(target=run_stream, daemon=True)
    llm_thread.start()

    async def stream_tokens():
        accumulated = ""
        deadline = time.monotonic() + 120  # 2-min hard timeout

        while True:
            try:
                tok = token_q.get_nowait()
                if tok is None:
                    break
                accumulated += tok
                yield _sse({"token": tok})
            except sync_queue.Empty:
                if time.monotonic() > deadline:
                    yield _sse({"error": "Response timed out."})
                    break
                await asyncio.sleep(0.02)  # 20 ms polling — imperceptible at Ollama token speed

        if not accumulated:
            yield _sse({"token": "I'm sorry, I couldn't generate a response. Please try again."})

        if holder and holder[0]:
            conversation_memory[conv_id].append(holder[0])

        yield _sse({"done": True, "conversation_id": conv_id})

    return StreamingResponse(stream_tokens(), media_type="text/event-stream")
