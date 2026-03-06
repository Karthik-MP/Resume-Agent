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

try:
    from google import genai
except ImportError:
    genai = None

from resume_agent.config import settings

logger = logging.getLogger(__name__)


class GeminiWrapper:
    """Wrapper to make Gemini API compatible with LangChain-style interface"""
    
    def __init__(self, api_key: str, model: str, temperature: float, max_tokens: int, timeout: int):
        if genai is None:
            raise ImportError(
                "google-genai not installed. "
                "Install it with: pip install google-genai"
            )
        
        # Create the client
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
    
    def invoke(self, messages: list) -> object:
        """Invoke Gemini model with messages in LangChain format"""
        from google.genai import types
        
        # Convert LangChain-style messages to Gemini format
        contents = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                # Gemini doesn't have a system role, prepend as user message
                contents.append(f"Instructions: {content}")
            else:
                contents.append(content)
        
        # Combine all parts into a single prompt
        full_prompt = "\n\n".join(contents)
        
        # Generate response
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens,
                )
            )
            
            # Check if response was blocked or empty
            if not response.text:
                raise ValueError("Empty response from Gemini API")
            
            # Return object with .content attribute to match LangChain interface
            class Response:
                def __init__(self, text):
                    self.content = text
            
            return Response(response.text)
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            # Re-raise with more context
            raise Exception(f"Gemini API call failed: {str(e)}")

# Global LLM instance (lazy initialization)
_llm_instance = None


def get_llm():
    """
    Get the configured LLM model (singleton pattern).
    Uses settings from environment variables or .env file.
    Supports multiple providers: OpenAI, Custom, and Gemini (future).
    """
    global _llm_instance

    if _llm_instance is None:
        # Validate settings
        settings.validate()

        provider = settings.LLM_PROVIDER
        api_key = settings.get_active_api_key()
        model = settings.get_active_model()

        if provider == "gemini":
            # Use Gemini provider
            logger.info(
                f"Initializing LLM: provider={provider}, model={model}, "
                f"temperature={settings.LLM_TEMPERATURE}"
            )
            
            _llm_instance = GeminiWrapper(
                api_key=api_key,
                model=model,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                # timeout=settings.LLM_TIMEOUT,
            )
        else:
            # For OpenAI and Custom providers, use ChatOpenAI client
            if ChatOpenAI is None:
                raise ImportError(
                    "langchain-openai not installed. "
                    "Install it with: pip install langchain-openai"
                )

            base_url = settings.get_active_base_url()

            logger.info(
                f"Initializing LLM: provider={provider}, model={model}, "
                f"base_url={base_url}, temperature={settings.LLM_TEMPERATURE}"
            )

            # Use standard OpenAI-compatible client for both OpenAI and Custom providers
            _llm_instance = ChatOpenAI(
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
                timeout=settings.LLM_TIMEOUT,
                streaming=False,
            )

    return _llm_instance


def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 2) -> str:
    """
    Call LLM with system and user prompts.

    Args:
        system_prompt: System instruction for the LLM
        user_prompt: User message/query
        max_retries: Maximum number of retries for rate limit errors

    Returns:
        LLM response as string

    Raises:
        ValueError: If API key is not configured
        Exception: If LLM call fails (quota exceeded or other errors)
    """
    import time
    
    llm = get_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    logger.debug(
        f"Calling LLM with system prompt length: {len(system_prompt)}, "
        f"user prompt length: {len(user_prompt)}"
    )
    
    # Debug: Print request details
    logger.info("=" * 60)
    logger.info("LLM REQUEST DEBUG")
    logger.info("=" * 60)
    logger.info(f"Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Model: {settings.get_active_model()}")
    logger.info(f"Base URL: {settings.get_active_base_url()}")
    logger.info(f"Temperature: {settings.LLM_TEMPERATURE}")
    logger.info(f"Max Tokens: {settings.LLM_MAX_TOKENS}")
    logger.info(f"Messages structure:")
    for i, msg in enumerate(messages):
        logger.info(f"  Message {i+1}:")
        logger.info(f"    Role: {msg['role']}")
        logger.info(f"    Content length: {len(msg['content'])} chars")
        logger.info(f"    Content preview: {msg['content'][:200]}...")
    logger.info("=" * 60)

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries}: Invoking LLM...")
            response = llm.invoke(messages)
            logger.debug(f"LLM response length: {len(response.content)}")
            
            # Check for empty response
            if not response.content or len(response.content.strip()) == 0:
                logger.error("=" * 60)
                logger.error("EMPTY RESPONSE FROM LLM API")
                logger.error("=" * 60)
                logger.error(f"Provider: {settings.LLM_PROVIDER}")
                logger.error(f"Model: {settings.get_active_model()}")
                logger.error(f"Base URL: {settings.get_active_base_url()}")
                logger.error(f"Response object: {response}")
                logger.error(f"Response content type: {type(response.content)}")
                logger.error(f"Response content repr: {repr(response.content)}")
                logger.error("=" * 60)
                logger.error("POSSIBLE CAUSES:")
                logger.error("1. Model may not be available through this API endpoint")
                logger.error("2. Model may require different parameters or headers")
                logger.error("3. API endpoint may not support this model")
                logger.error("=" * 60)
                logger.error("RECOMMENDED SOLUTIONS:")
                logger.error("1. Switch to Gemini: Set LLM_PROVIDER=gemini in .env")
                logger.error("2. Switch to OpenAI: Set LLM_PROVIDER=openai in .env")
                logger.error("3. Use Moonshot directly: Set LLM_PROVIDER=moonshot in .env")
                logger.error("=" * 60)
                raise Exception(
                    f"EMPTY_RESPONSE: LLM returned empty response. "
                    f"Model '{settings.get_active_model()}' may not be available through {settings.get_active_base_url()}. "
                    f"Try switching to gemini, openai, or moonshot provider."
                )
            
            logger.info("LLM call successful")
            logger.debug(f"Response preview: {response.content[:200]}...")
            return response.content

        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM call failed on attempt {attempt + 1}: {error_msg}")
            
            # Log additional error details for debugging
            if hasattr(e, '__dict__'):
                logger.error(f"Error details: {e.__dict__}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {getattr(e.response, 'status_code', 'N/A')}")
                logger.error(f"Response headers: {getattr(e.response, 'headers', 'N/A')}")
                logger.error(f"Response body: {getattr(e.response, 'text', 'N/A')[:500]}")
            
            # Check if this is a quota exceeded error (should stop immediately)
            if "insufficient_quota" in error_msg.lower() or "quota exceeded" in error_msg.lower():
                logger.error(f"LLM quota exceeded: {e}")
                logger.error("Your API quota has been exhausted. Please check your billing details.")
                raise Exception(f"QUOTA_EXCEEDED: {error_msg}")
            
            # Check if this is a rate limit error (should retry once, then fail)
            if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = 10  # Reduced from 20 to 10 seconds
                    logger.warning(f"Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Rate limit persisted after {max_retries} attempts: {e}")
                    logger.error("Stopping process due to repeated rate limit errors. Check your API quota/billing.")
                    raise Exception(f"RATE_LIMIT_EXCEEDED: {error_msg}")
            
            # Other errors should be raised immediately
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
