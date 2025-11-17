from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.callbacks.manager import CallbackManager


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

load_dotenv()

AI_PROVIDER = "abacus"  #os.getenv("AI_PROVIDER", "openai")

# Abacus
ABACUS_API_KEY = os.getenv("ABACUS_API_KEY", "")
ABACUS_API_BASE = os.getenv("ABACUS_API_BASE", "https://routellm.abacus.ai/v1")
ABACUS_MODEL = os.getenv("ABACUS_MODEL", "route-llm")

llm = ChatOpenAI(
    openai_api_key=ABACUS_API_KEY,
    model=ABACUS_MODEL,
    base_url=ABACUS_API_BASE,
    streaming=True,
    temperature=0.7,
   # model_kwargs={"callback_manager": CallbackManager([controller])}
)

prompt = """Explain me about python programming, in less than 200 words"""
def stream_ai_response(prompt):
    for chunk in llm.stream(prompt):
        if chunk.content:
            yield chunk.content

for token in stream_ai_response(prompt):
    print(token,end="",flush="")
