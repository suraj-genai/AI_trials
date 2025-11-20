# BackEnd/core/ai_agent.py
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from core.config import (
    AI_PROVIDER,
    OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL,
    ABACUS_API_KEY, ABACUS_API_BASE, ABACUS_MODEL
)

# System prompt for journaling assistant
SYSTEM_PROMPT = """
You are a warm, empathetic journaling assistant. 
Help users reflect on their thoughts and feelings.
Be supportive, ask thoughtful questions, and encourage self-discovery.
Keep responses concise but meaningful.
"""

class JournalAgent:
    """Singleton journal agent with persistent LLM"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Initialize LLM once
        if AI_PROVIDER.lower() == "openai":
            self.llm = ChatOpenAI(
                openai_api_key=OPENAI_API_KEY,
                model=OPENAI_MODEL,
                base_url=OPENAI_API_BASE,
                streaming=True,
                temperature=1,
                timeout=30
            )
        elif AI_PROVIDER.lower() == "abacus":
            self.llm = ChatOpenAI(
                openai_api_key=ABACUS_API_KEY,
                model=ABACUS_MODEL,
                base_url=ABACUS_API_BASE,
                streaming=True,
                temperature=0.7,
                timeout=30
            )
        else:
            raise ValueError("Invalid AI provider in .env")

        self._initialized = True
        print(f"✅ JournalAgent initialized with {AI_PROVIDER} provider")

    def stream_response(self, message, conversation_history):
        """
        Stream AI response given message and history

        Args:
            message (str): User's current message
            conversation_history (list): List of {role, content} dicts

        Yields:
            str: Chunks of AI response
        """
        # Convert history to LangChain format
        messages = []

        # System prompt
        system_prompt = """You are a thoughtful journaling companion.   
        Help users reflect on their day, identify patterns, and gain insights.  
        Ask meaningful questions. Be empathetic and supportive."""

        messages.append(HumanMessage(content=f"System: {system_prompt}"))

        # Add conversation history
        for msg in conversation_history:
            if msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))

                # Add current message
        messages.append(HumanMessage(content=message))
        try:
            # Stream response
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content

        except Exception as e:
            print(f"Error in stream_response: {e}")
            error_msg = f"\n\n[Error: {str(e)}]"
            yield error_msg



# Create singleton instance at module load
agent = JournalAgent()