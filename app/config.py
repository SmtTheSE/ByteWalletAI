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

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # AI mode: "local_only" | "rules_only"
    ai_default_mode: str = "local_only"

    # Model artifacts
    model_path: str = "models/burn_rate_model.pkl"
    feature_config_path: str = "models/feature_config.json"


settings = Settings()
