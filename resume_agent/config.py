"""
Configuration settings for Resume Agent
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Main application settings"""
    
    # OpenAI API Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    # LLM Configuration
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "60"))
    
    # Application Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def validate(self) -> bool:
        """Validate required settings"""
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required. Set it in .env file or environment variables.")
        
        if self.LLM_TEMPERATURE < 0 or self.LLM_TEMPERATURE > 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")
        
        if self.LLM_MAX_TOKENS <= 0:
            raise ValueError("LLM_MAX_TOKENS must be positive")
            
        return True


# Global settings instance
settings = Settings()
