"""
Configuration settings for Resume Agent
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Main application settings"""

    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv(
        "LLM_PROVIDER", "openai"
    )  # Options: openai, custom, gemini, moonshot

    # OpenAI API Configuration (ChatGPT)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Custom Model Configuration (for deployed models)
    CUSTOM_API_KEY: str = os.getenv("CUSTOM_API_KEY", "")
    CUSTOM_BASE_URL: str = os.getenv("CUSTOM_BASE_URL", "")
    CUSTOM_MODEL: str = os.getenv("CUSTOM_MODEL", "")

    # Moonshot AI Configuration
    MOONSHOT_API_KEY: str = os.getenv("MOONSHOT_API_KEY", "")
    MOONSHOT_BASE_URL: str = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.ai/v1")
    MOONSHOT_MODEL: str = os.getenv("MOONSHOT_MODEL", "kimi-k2-turbo-preview")

    # Gemini Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # LLM Configuration
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "60"))

    # Application Settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def get_active_api_key(self) -> str:
        """Get API key based on selected provider"""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "custom":
            return self.CUSTOM_API_KEY
        elif self.LLM_PROVIDER == "moonshot":
            return self.MOONSHOT_API_KEY
        elif self.LLM_PROVIDER == "gemini":
            return self.GEMINI_API_KEY
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")

    def get_active_base_url(self) -> str:
        """Get base URL based on selected provider"""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_BASE_URL
        elif self.LLM_PROVIDER == "custom":
            return self.CUSTOM_BASE_URL
        elif self.LLM_PROVIDER == "moonshot":
            return self.MOONSHOT_BASE_URL
        elif self.LLM_PROVIDER == "gemini":
            return ""  # Gemini uses different client
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")

    def get_active_model(self) -> str:
        """Get model name based on selected provider"""
        if self.LLM_PROVIDER == "openai":
            return self.OPENAI_MODEL
        elif self.LLM_PROVIDER == "custom":
            return self.CUSTOM_MODEL
        elif self.LLM_PROVIDER == "moonshot":
            return self.MOONSHOT_MODEL
        elif self.LLM_PROVIDER == "gemini":
            return self.GEMINI_MODEL
        else:
            raise ValueError(f"Unknown LLM provider: {self.LLM_PROVIDER}")

    def validate(self) -> bool:
        """Validate required settings based on provider"""
        # Validate provider
        valid_providers = ["openai", "custom", "moonshot", "gemini"]
        if self.LLM_PROVIDER not in valid_providers:
            raise ValueError(f"LLM_PROVIDER must be one of: {valid_providers}")

        # Validate API key based on provider
        if self.LLM_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider.")
        elif self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider.")
        elif self.LLM_PROVIDER == "custom":
            if not self.CUSTOM_API_KEY:
                raise ValueError(
                    "CUSTOM_API_KEY is required when using custom provider."
                )
            if not self.CUSTOM_BASE_URL:
                raise ValueError(
                    "CUSTOM_BASE_URL is required when using custom provider."
                )
            if not self.CUSTOM_MODEL:
                raise ValueError("CUSTOM_MODEL is required when using custom provider.")
        elif self.LLM_PROVIDER == "moonshot" and not self.MOONSHOT_API_KEY:
            raise ValueError("MOONSHOT_API_KEY is required when using Moonshot provider.")
        elif self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider.")

        # Validate temperature and tokens
        if self.LLM_TEMPERATURE < 0 or self.LLM_TEMPERATURE > 2:
            raise ValueError("LLM_TEMPERATURE must be between 0 and 2")

        if self.LLM_MAX_TOKENS <= 0:
            raise ValueError("LLM_MAX_TOKENS must be positive")

        return True


# Global settings instance
settings = Settings()
