"""
app/config.py
Centralised settings loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        protected_namespaces=(),   # suppress model_ namespace warning
    )

    # AI mode: "auto" | "local_only" | "rules_only"
    ai_default_mode: str = "rules_only"

    # Model artifacts
    model_path: str = "models/burn_rate_model.pkl"
    feature_config_path: str = "models/feature_config.json"

    # Phase 1: Gemini LLM (NL Function Calling)
    gemini_api_key: str = ""              # Set GEMINI_API_KEY in .env
    gemini_model: str = "gemini-2.0-flash"

    # Phase 2: RAG (Vector store)
    rag_enabled: bool = True
    rag_top_k: int = 5                   # Number of relevant transactions to retrieve


settings = Settings()
