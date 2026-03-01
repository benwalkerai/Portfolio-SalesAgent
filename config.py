"""
Configuration module for the AI Sales Agent Application.

Author: Ben Walker (BenRWalker@icloud.com)
"""

import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from agents import set_tracing_disabled
from logger_config import setup_logger

logger = setup_logger(__name__)
set_tracing_disabled(True)
logger.info("Tracing disabled (local-only mode)")

def setup_env():
    """Load environment variables from the local .env file."""
    load_dotenv()
    logger.info("Environment variables loaded from .env file")


def _require_env(var_name: str) -> str:
    """Return the value of a required environment variable or raise an error."""
    value = os.environ.get(var_name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable '{var_name}'. "
            "Ensure your .env or deployment config defines it before starting the app."
        )
    return value

LLM_API_KEY = _require_env('LLM_API_KEY')
LLM_API_URL = _require_env('LLM_API_URL')

logger.info(f"Configuration module initialized with base url: {LLM_API_URL}")

try:
    ollama_client = AsyncOpenAI(
        base_url=LLM_API_URL,
        api_key=LLM_API_KEY
    )
    logger.info("Ollama client configured successfully")
except Exception as e:
    logger.error(
        "Failed to configure Ollama client. Double-check that the URL/token are valid and reachable.",
        exc_info=True
    )
    raise