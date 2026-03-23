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

    # ── Core AI mode ───────────────────────────────────────────────────────
    # Options: "rules_only" | "local_only" | "auto"
    ai_default_mode: str = "rules_only"
    
    # Voice Provider: "gemini" | "ollama"
    ai_voice_provider: str = "ollama"

    # ── Model artifacts ──────────────────────────────────────────────────────
    model_path: str = "models/burn_rate_model.pkl"
    feature_config_path: str = "models/feature_config.json"

    # ── Phase 2: RAG (Vector store) ──────────────────────────────────────────
    rag_enabled: bool = True
    rag_top_k: int = 5                   # Number of relevant transactions to retrieve

    # ── Ollama (Local Voice Fallback) ───────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:latest"

    # ── Security & Production Settings ────────────────────────────────────────
    # CORS: Comma-separated list of allowed origins. Use "*" only for dev.
    # Example: "https://wallet.example.com,https://app.example.com"
    cors_origins: str = "*"
    
    # API Authentication: Comma-separated list of valid API keys
    # If empty, API auth is disabled (dev mode). Set for production.
    # Example: "prod-key-abc123,prod-key-xyz789"
    api_keys: str = ""
    
    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Format: "number/period" e.g., "100/minute", "1000/hour"
    rate_limit: str = "100/minute"
    
    # ── Federated Learning ───────────────────────────────────────────────────
    # Set min clients before FedAvg aggregation triggers (default: 3)
    fed_min_clients: int = 3
    
    # ── Project Root ──────────────────────────────────────────────────────────
    # Optional: override the auto-detected project root path
    project_root: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @property
    def api_keys_list(self) -> list[str]:
        """Parse API keys string into list."""
        if not self.api_keys:
            return []
        return [key.strip() for key in self.api_keys.split(",") if key.strip()]
    
    @property
    def api_auth_enabled(self) -> bool:
        """Check if API authentication is enabled."""
        return len(self.api_keys_list) > 0
    
    @property
    def rate_limit_parts(self) -> tuple[int, str]:
        """Parse rate limit string into (number, period)."""
        parts = self.rate_limit.split("/")
        if len(parts) != 2:
            return (100, "minute")
        try:
            number = int(parts[0].strip())
        except ValueError:
            number = 100
        period = parts[1].strip().lower()
        return (number, period)


settings = Settings()
