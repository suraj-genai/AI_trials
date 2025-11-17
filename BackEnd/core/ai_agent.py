# core/ai_agent.py
from langchain_community.chat_models import ChatOpenAI
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.callbacks.manager import CallbackManager
from core.config import (
    AI_PROVIDER,
    OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL,
    ABACUS_API_KEY, ABACUS_API_BASE, ABACUS_MODEL
)


class StreamingController(BaseCallbackHandler):
    """Handles streaming + interrupt control."""
    def __init__(self):
        self.buffer = ""
        self.stop_flag = False
        self.on_token = None

    def on_llm_new_token(self, token: str, **kwargs):
        if self.stop_flag:
            raise GeneratorExit("Stopped by user.")
        self.buffer += token
        if self.on_token:
            self.on_token(token)


controller = StreamingController()


def get_llm():
    """Factory to get configured LLM based on provider."""
    if AI_PROVIDER.lower() == "openai":
        return ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            base_url=OPENAI_API_BASE,
            streaming=True,
            temperature=1,
            timeout=30
          #  model_kwargs={"callback_manager":CallbackManager([controller])}
        )

    elif AI_PROVIDER.lower() == "abacus":
        return ChatOpenAI(
            openai_api_key=ABACUS_API_KEY,
            model=ABACUS_MODEL,
            base_url=ABACUS_API_BASE,
            streaming=True,
            temperature=0.7,
            timeout=30
           # model_kwargs={"callback_manager":CallbackManager([controller])}
        )

    else:
        raise ValueError("Invalid AI provider in .env")


def stream_ai_response(prompt: str):
    """Generator to stream AI response."""
    llm = get_llm()
    controller.stop_flag = False

    try:
        for chunk in llm.stream(prompt):
            if chunk and chunk.content:
                safe_chunk = chunk.content #.replace("\n", "\\n").replace("\r", "")
                yield safe_chunk
        yield "[END]\n\n"
    except GeneratorExit:
        yield "\n\n[Generation stopped by user]\n"
    except Exception as e:
        yield f"\n\n[Error: {str(e)}]\n"
