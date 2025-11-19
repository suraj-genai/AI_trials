import os
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = "abacus" #os.getenv("AI_PROVIDER", "openai")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# Abacus
ABACUS_API_KEY = os.getenv("ABACUS_API_KEY", "")
ABACUS_API_BASE = os.getenv("ABACUS_API_BASE", "https://routellm.abacus.ai/v1")
ABACUS_MODEL = os.getenv("ABACUS_MODEL", "gpt-5 mini")
