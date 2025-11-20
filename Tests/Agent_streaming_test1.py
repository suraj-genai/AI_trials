import asyncio
from typing import Dict, Any, AsyncIterable, Optional

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.agents import create_agent  # Using the newer create_agent
from dotenv import load_dotenv
import os

load_dotenv()


class InterruptHandler(AsyncCallbackHandler):
    def __init__(self):
        self.cancelled = False

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if self.cancelled:
            raise asyncio.CancelledError("Stream interrupted")


class SmartAgent:
    def __init__(
            self,
            system_prompt: str = (
                    "You are a helpful assistant. "
                    "Reason step-by-step. "
                    "Use the Web Search tool only if the query requires real-time or external information. "
                    "Otherwise, answer directly from knowledge."
            ),
            model: str = "route-llm",
            api_base: str = "https://routellm.abacus.ai/v1",
            api_key: str = os.getenv("ABACUS_API_KEY", ""),
    ):
        self.system_prompt = system_prompt
        self.history = ChatMessageHistory()
        self.llm = ChatOpenAI(
            model=model,
            base_url=api_base,
            openai_api_key=api_key,
            temperature=0.7,
            streaming=True,
        )
        # FIX: Tool name must match pattern ^[a-zA-Z0-9_-]+$
        self.tools = [DuckDuckGoSearchRun(name="Web Search")]

        # Using create_agent (newer API)
        self.agent_graph = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        )

        self._queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.interrupt_handler = InterruptHandler()
        self._debug = True  # Enable debug mode to see all events

    async def _stream_response(self, user_input: str):
        self.history.add_user_message(user_input)
        config = {"callbacks": [self.interrupt_handler]}

        try:
            async for event in self.agent_graph.astream_events(
                    {"messages": self.history.messages},
                    version="v2",
                    config=config,
            ):
                kind = event["event"]
                name = event.get("name", "")

                # Debug: Print all events to understand what's happening
                if self._debug:
                    print(f"[DEBUG] Event: {kind} | Name: {name}")

                # === CHAIN EVENTS ===
                if kind == "on_chain_start":
                    if "agent" in name.lower():
                        await self._queue.put({"type": "agent_start", "content": "Agent started..."})

                elif kind == "on_chain_stream":
                    # Intermediate chain outputs
                    pass

                elif kind == "on_chain_end":
                    if "agent" in name.lower():
                        await self._queue.put({"type": "agent_end", "content": "Agent finished"})

                # === LLM/CHAT MODEL EVENTS ===
                elif kind == "on_llm_start" or kind == "on_chat_model_start":
                    await self._queue.put({"type": "thinking", "content": "Thinking..."})

                elif kind == "on_llm_stream" or kind == "on_chat_model_stream":
                    # This is where the actual token streaming happens
                    chunk = event["data"].get("chunk")
                    if chunk:
                        content = ""
                        # Handle different chunk types
                        if hasattr(chunk, "content"):
                            content = chunk.content
                        elif isinstance(chunk, dict):
                            content = chunk.get("content", "")
                        elif isinstance(chunk, str):
                            content = chunk

                        if content:
                            await self._queue.put({"type": "token", "content": content})

                elif kind == "on_llm_end" or kind == "on_chat_model_end":
                    # LLM finished generating
                    pass

                # === TOOL EVENTS ===
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event["data"].get("input", {})
                    await self._queue.put({
                        "type": "tool_start",
                        "content": f"🔧 Calling tool: {tool_name}",
                        "tool_name": tool_name,
                        "tool_input": tool_input
                    })

                elif kind == "on_tool_stream":
                    # Some tools stream their output
                    pass

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event["data"].get("output", "")
                    await self._queue.put({
                        "type": "tool_end",
                        "content": f"✅ Tool {tool_name} completed",
                        "tool_output": str(tool_output)[:200]  # Truncate long outputs
                    })

                # === RETRIEVER EVENTS (if you add RAG later) ===
                elif kind == "on_retriever_start":
                    await self._queue.put({"type": "retrieval_start", "content": "Searching knowledge base..."})

                elif kind == "on_retriever_end":
                    docs = event["data"].get("output", [])
                    await self._queue.put({
                        "type": "retrieval_end",
                        "content": f"Found {len(docs)} relevant documents"
                    })

                # === CATCH-ALL for unknown events ===
                else:
                    if self._debug:
                        await self._queue.put({
                            "type": "unknown_event",
                            "content": f"Unhandled event: {kind}",
                            "event_data": event
                        })

            await self._queue.put({"type": "done"})

        except asyncio.CancelledError:
            await self._queue.put({"type": "cancelled", "content": "Stream cancelled by user"})
            raise

        except Exception as e:
            await self._queue.put({"type": "error", "content": f"Error: {str(e)}"})
            if self._debug:
                import traceback
                await self._queue.put({"type": "error_trace", "content": traceback.format_exc()})

        finally:
            await self._queue.put(None)  # Sentinel

    async def start_stream(self, user_input: str):
        async with self._lock:
            if self._task and not self._task.done():
                raise RuntimeError("Already streaming. Call cancel() first.")
            # Clear the queue from previous runs
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self._task = asyncio.create_task(self._stream_response(user_input))

    async def get_stream(self) -> AsyncIterable[Dict[str, Any]]:
        if not self._task:
            raise RuntimeError("Call start_stream() first")

        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item

    async def cancel(self):
        """Cancel the current streaming task"""
        self.interrupt_handler.cancelled = True
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                finally:
                    self._task = None
                    self.interrupt_handler.cancelled = False

    def set_debug(self, debug: bool):
        """Enable/disable debug mode to see all events"""
        self._debug = debug


# Comprehensive test function
async def test_agent():
    agent = SmartAgent()
    agent.set_debug(True)  # See all events

    print("\n" + "=" * 60)
    print("TEST 1: Simple question (no tool needed)")
    print("=" * 60)
    await agent.start_stream("What is 2+2?")
    async for chunk in agent.get_stream():
        if chunk["type"] == "token":
            print(chunk["content"], end="", flush=True)
        else:
            print(f"\n[{chunk['type'].upper()}] {chunk.get('content', '')}")
    print("\n")

    print("\n" + "=" * 60)
    print("TEST 2: Question requiring web search")
    print("=" * 60)
    await agent.start_stream("What is the current weather in Tokyo?")
    async for chunk in agent.get_stream():
        if chunk["type"] == "token":
            print(chunk["content"], end="", flush=True)
        else:
            print(f"\n[{chunk['type'].upper()}] {chunk.get('content', '')}")
    print("\n")

    print("\n" + "=" * 60)
    print("TEST 3: Cancellation test")
    print("=" * 60)
    await agent.start_stream("Write a 5000 word essay on the history of computing.")

    async def consume_with_timeout():
        count = 0
        async for chunk in agent.get_stream():
            if chunk["type"] == "token":
                print(chunk["content"], end="", flush=True)
                count += 1
                if count > 50:  # Cancel after 50 tokens
                    break
            else:
                print(f"\n[{chunk['type'].upper()}] {chunk.get('content', '')}")

    stream_task = asyncio.create_task(consume_with_timeout())
    await asyncio.sleep(2)
    print("\n\n🛑 CANCELLING...")
    await agent.cancel()

    try:
        await stream_task
    except asyncio.CancelledError:
        print("✅ Stream cancelled successfully")
    print("\n")


if __name__ == "__main__":
    asyncio.run(test_agent())