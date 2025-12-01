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

    def stream_response(self, message, conversation_history, user_context=""):
        """
        Stream AI response with long-term memory context
        """
        messages = []

        # 1. Dynamic System Prompt
        # We enforce brevity and the "One Question Rule" here.
        system_instructions = """
        You are a warm, empathetic journaling assistant named Memory Grove.

        CORE RULES:
        1. Keep responses CONCISE (max 3-4 sentences usually).
        2. Ask ONLY ONE thoughtful question at a time to keep the user focused.
        3. Never overwhelm the user with a list of questions.
        4. If the user mentions a significant event, acknowledge it deeply before moving on.
        """

        if not user_context:
            # FIRST TIME USER
            context_prompt = """
            This is the first time you are meeting this user.
            Gently introduce yourself and get to know about them and their intentions with an AI journal.
            """
        else:
            # RETURNING USER
            context_prompt = f"""
            LONG TERM MEMORY (Context):
            {user_context}

            INSTRUCTION:
            Use the context to personalize your response. 
            If the user has been away, welcome them back warmly.
            Check on specific things mentioned in the memory (e.g., "How did that project go?").
            """

        full_system_prompt = f"{system_instructions}\n\n{context_prompt}"
        messages.append(SystemMessage(content=full_system_prompt))

        # 2. Add History
        for msg in conversation_history:
            if msg.get('role') == 'user':
                messages.append(HumanMessage(content=msg.get('content', '')))
            elif msg.get('role') == 'assistant':
                messages.append(AIMessage(content=msg.get('content', '')))

        # 3. Add Current Message
        # Special logic: If the frontend sends a specific trigger for greeting, we handle it as a system instruction
        if message.startswith("[SYSTEM_TRIGGER_GREETING]"):
            # This is the "hidden" prompt for the greeting
            greeting_instruction = """
             The user has just opened their journal for the day. 
             Based on the time of day and the Long Term Memory, greet them warmly.
             If there is a specific concern in the memory (e.g., they were sick), ask about it.
             Otherwise, ask: "How are you feeling today?"
             """
            messages.append(HumanMessage(content=greeting_instruction))
        else:
            messages.append(HumanMessage(content=message))

        try:
            for chunk in self.llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
        except Exception as e:
            print(f"Error in stream: {e}")
            yield f"[Error: {str(e)}]"

    def generate_daily_summary(self, current_chat_text, previous_summary=""):
        """
        Merge previous summary with today's chat to create an updated User Profile.
        """

        prompt = f"""
        You are the 'Memory Manager' for a personal journal.

        GOAL: Create an updated, detailed summary of the user's life, patterns, and mental state.

        INPUTS:
        1. PREVIOUS MEMORY (Context from past days):
        "{previous_summary}"

        2. TODAY'S ENTRY:
        "{current_chat_text}"

        INSTRUCTIONS:
        - Combine the Previous Memory and Today's Entry into a SINGLE cohesive narrative.
        - Retain important long-term facts (names, goals, recurring struggles).
        - Add new insights from today.
        - If today's entry contradicts old memory, update it (people change).
        - The output must be detailed but organized (up to 1000 tokens is fine, but be efficient).
        - Do not use meta-language like "The user said...". Write it as a profile: "User is feeling... User is working on..."
        """

        messages = [HumanMessage(content=prompt)]

        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            return f"Error generating summary: {e}"



# Create singleton instance at module load
agent = JournalAgent()