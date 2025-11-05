from langchain_community.chat_models import ChatOpenAI
from config import (
    AI_PROVIDER,
    OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL,
    ABACUS_API_KEY, ABACUS_API_BASE, ABACUS_MODEL
)

def get_ai_response(prompt: str) -> str:
    """Unified AI gateway for OpenAI and Abacus.ai"""

    if AI_PROVIDER.lower() == "openai":
        llm = ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            base_url=OPENAI_API_BASE,
            temperature=0.7,
        )
        return llm.invoke(prompt).content

    elif AI_PROVIDER.lower() == "abacus":
        llm = ChatOpenAI(
            openai_api_key=ABACUS_API_KEY,
            model=ABACUS_MODEL,
            base_url=ABACUS_API_BASE,
            temperature=0.7,
        )
        return llm.invoke(prompt).content

    else:
        return "Invalid AI provider selected. Please set AI_PROVIDER in .env."
