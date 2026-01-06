# resume_agent/tools.py
import os
import logging
import requests
from bs4 import BeautifulSoup

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None
try:
    from ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

from resume_agent.config import settings

logger = logging.getLogger(__name__)

# Global LLM instance (lazy initialization)
_llm_instance = None


def get_llm():
    """
    Get the configured LLM model (singleton pattern).
    Uses settings from environment variables or .env file.
    """
    global _llm_instance
    
    if _llm_instance is None:
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai not installed. "
                "Install it with: pip install langchain-openai"
            )
        
        # Validate settings
        settings.validate()
        
        logger.info(f"Initializing LLM: model={settings.OPENAI_MODEL}, "
                   f"base_url={settings.OPENAI_BASE_URL}, "
                   f"temperature={settings.LLM_TEMPERATURE}")
        
        _llm_instance = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT
        )
    
    return _llm_instance


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """
    Call LLM with system and user prompts.
    
    Args:
        system_prompt: System instruction for the LLM
        user_prompt: User message/query
        
    Returns:
        LLM response as string
        
    Raises:
        ValueError: If API key is not configured
        Exception: If LLM call fails
    """
    try:
        llm = get_llm()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.debug(f"Calling LLM with system prompt length: {len(system_prompt)}, "
                    f"user prompt length: {len(user_prompt)}")
        
        response = llm.invoke(messages)
        
        logger.debug(f"LLM response length: {len(response.content)}")
        
        return response.content
        
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise



def web_search(query: str, max_results: int = 5):
    """Perform a web search using Tavily if available, otherwise use DDGS."""
    query = query.strip()
    if not query:
        return {"text": "", "sources": []}
    api_key = os.environ.get("TAVILY_API_KEY")
    if api_key and TavilyClient:
        client = TavilyClient(api_key=api_key)
        try:
            response = client.search(query)
            results = response.get("results", [])
            text = " ".join(item.get("text", "") for item in results)
            sources = [item.get("url") for item in results if item.get("url")]
            return {"text": text, "sources": sources}
        except Exception:
            pass
    # Fallback to DDGS
    if DDGS:
        try:
            ddgs_client = DDGS()
            results = ddgs_client.text(query, max_results=max_results)
            text = " ".join(res.get("body", "") for res in results if res.get("body"))
            sources = [res.get("href") for res in results if res.get("href")]
            return {"text": text, "sources": sources}
        except Exception:
            pass
    # If all fails, attempt direct requests (DuckDuckGo HTML)
    try:
        url = f"https://duckduckgo.com/html/?q={query}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = [p.get_text() for p in soup.find_all("p")]
        text = " ".join(paragraphs)
        return {"text": text, "sources": []}
    except Exception:
        return {"text": "", "sources": []}


def fetch_page_text(url: str):
    """Fetch page and extract text."""
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        texts = [p.get_text() for p in soup.find_all(["p", "h1", "h2", "h3"])]
        return "\n".join(texts)
    except Exception:
        return ""
