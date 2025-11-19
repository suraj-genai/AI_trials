# BackEnd/core/ai_agent.py
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage
from core.config import (
    AI_PROVIDER,
    OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL,
    ABACUS_API_KEY, ABACUS_API_BASE, ABACUS_MODEL
)
from core.database import db
# System prompt for journaling assistant
SYSTEM_PROMPT = """
You are a warm, empathetic journaling assistant. 
Help users reflect on their thoughts and feelings.
Be supportive, ask thoughtful questions, and encourage self-discovery.
Keep responses concise but meaningful.
"""

# In-memory conversation storage (keyed by date)
conversation_memory = {}


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

    def get_conversation_history(self, date: str):
        """Get conversation history for a specific date from database"""
        if date not in conversation_memory:
            # Load from database
            messages_from_db = db.get_messages(date)

            # Convert to LangChain message format
            conversation_memory[date] = [SystemMessage(content=SYSTEM_PROMPT)]

            for msg in messages_from_db:
                if msg['role'] == 'user':
                    conversation_memory[date].append(HumanMessage(content=msg['content']))
                elif msg['role'] == 'assistant':
                    conversation_memory[date].append(AIMessage(content=msg['content']))

        return conversation_memory[date]

    def add_to_conversation(self, date: str, role: str, content: str):
        """Add a message to conversation history AND database"""
        history = self.get_conversation_history(date)

        if role == "user":
            history.append(HumanMessage(content=content))
        elif role == "assistant":
            history.append(AIMessage(content=content))

            # Save to database
        db.save_message(date, role, content)

    async def stream_response(self, message: str, date: str):
        """
        Stream AI response token by token with conversation memory

        Args:
            message: User's message string
            date: Date string (YYYY-MM-DD) to maintain separate conversations per day

        Yields:
            str: Individual tokens from the AI response
        """
        # Get conversation history for this date
        history = self.get_conversation_history(date)

        # Add user message to history
        self.add_to_conversation(date, "user", message)

        # Collect full response for adding to history later
        full_response = ""

        try:
            # Stream directly from LLM with conversation history
            async for chunk in self.llm.astream(history):
                print(chunk)
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content
            print("Full Response = ",full_response)
            # Add AI response to conversation history
            self.add_to_conversation(date, "assistant", full_response)

        except Exception as e:
            print(f"Error in stream_response: {e}")
            error_msg = f"\n\n[Error: {str(e)}]"
            full_response += error_msg
            yield error_msg
            if full_response.strip():
                self.add_to_conversation(date, "assistant", full_response)

    def clear_conversation(self, date: str):
        """Clear conversation history for a specific date"""
        if date in conversation_memory:
            del conversation_memory[date]

    def get_all_messages(self, date: str):
        """Get all messages for a date (for loading previous conversations)"""
        history = self.get_conversation_history(date)
        messages = []
        for msg in history:
            if isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        return messages


# Create singleton instance at module load
agent = JournalAgent()