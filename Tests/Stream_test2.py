from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.messages import HumanMessage
from dotenv import load_dotenv
import os
import asyncio

print("Program started....")
load_dotenv()
AI_PROVIDER = "abacus"  #os.getenv("AI_PROVIDER", "openai")

# Abacus
ABACUS_API_KEY = os.getenv("ABACUS_API_KEY", "")
ABACUS_API_BASE = os.getenv("ABACUS_API_BASE", "https://routellm.abacus.ai/v1")
ABACUS_MODEL = os.getenv("ABACUS_MODEL", "gpt-5 mini")
print("ABACUS MODEL = ", ABACUS_MODEL)
llm = ChatOpenAI(
    openai_api_key=ABACUS_API_KEY,
    model=ABACUS_MODEL,
    base_url=ABACUS_API_BASE,
    streaming=True,
    temperature=0.7,
   # model_kwargs={"callback_manager": CallbackManager([controller])}
)
sys_prompt = """
You are a highly efficient AI Assistant.
"""
print("LLM Initialized")
agent = create_agent(llm,system_prompt=sys_prompt, tools=[] )
print("Agent1 initialized")


async def AI_stream_message(agent, message):
    count = 0
    async for content in agent.astream(message):
        count += 1
        print(count, content)
        # if content["event"] == "on_chat_model_stream":
        #     print(count, content['event'], ": ",content["data"]["chunk"])
        # elif content["event"] == "on_chain_start":
        #     print(count, content)
        # else:
        #     print(count, content['event'])

prompt = HumanMessage("Explain python programming in less than 200 words.")
print("Transmitting the message1")
asyncio.run(AI_stream_message(agent, prompt))