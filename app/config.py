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
    
    # Voice Provider: "gemini" | "ollama"
    ai_voice_provider: str = "ollama"

    # Model artifacts
    model_path: str = "models/burn_rate_model.pkl"
    feature_config_path: str = "models/feature_config.json"

    # Phase 2: RAG (Vector store)
    rag_enabled: bool = True
    rag_top_k: int = 5                   # Number of relevant transactions to retrieve

    # Ollama (Local Voice Fallback)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"


settings = Settings()
