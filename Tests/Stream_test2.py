from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_community.tools import GoogleSearchRun
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
ABACUS_MODEL = os.getenv("ABACUS_MODEL", "route-llm")

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
sys_prompt2 = """
You are an agent which can perform realtime google searches from the toolkit attached to you.
"""
tools = [GoogleSearchRun()]
agent2 = create_agent(llm, system_prompt=sys_prompt2, tools=tools)
print("Agent2 initialized")
prompt = {"messages": [{"role":"user","content":"Explain me about python programming, in less than 200 words"}]}
prompt2 = HumanMessage("What is the latest price of Gold/kg in INR? Which has a higher returns rate, Gold or Bitcoin?")
count = 0

async def AI_stream_message(agent, message):
    count = 0
    async for content in agent.astream_events(message,
                                              version="v2"):
        count += 1
        if content["event"] == "on_chat_model_stream":
            print(count, content['event'], ": ",content["data"]["chunk"].content)
        elif content["event"] == "on_chain_start":
            print(count, content)
        else:
            print(count, content['event'])

async def AI_search_stream(agent, prompt):
    count = 0
    async for content in agent.astream_events(prompt, version="v2"):
        count += 1
        if content["event"] == "on_chat_model_stream":
            print(count, content['event'],": ",content["data"]["chunk"].content)
        else:
            print(count, content)

print("Transmitting the message1")
asyncio.run(AI_stream_message(agent, prompt))
print("Transmitting the search message")
asyncio.run(AI_search_stream(agent2, prompt2))