from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL
    database_url: SecretStr = SecretStr("postgresql+asyncpg://tourism:tourism_pass@localhost:5432/tourism")

    # Chroma
    chroma_persist_dir: str = "./chroma_db"
    chroma_collection_name: str = "tourism_docs"

    # LLM Provider
    llm_provider: Literal["gemini", "gigachat", "groq", "mistral", "deepseek", "openrouter"] = "mistral"

    # Google Gemini API
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_max_tokens: int = 2048
    gemini_temperature: float = 0.3

    # GigaChat API
    gigachat_model: str = "GigaChat-2"
    gigachat_max_tokens: int = 2048
    gigachat_temperature: float = 0.2
    gigachat_top_p: float = 0.9
    gigachat_repetition_penalty: float = 1.1

    # Groq API
    groq_api_key: SecretStr | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 2048
    groq_temperature: float = 0.2  # Groq tool-use best practice (console.groq.com/docs/prompting)

    # Mistral API
    mistral_api_key: SecretStr | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-large-latest"
    mistral_model_fast: str = "ministral-8b-latest"
    mistral_model_balanced: str = "mistral-small-latest"
    mistral_max_tokens: int = 4096
    mistral_temperature: float = 0.3
    mistral_top_p: float = 0.9
    mistral_temp_extraction: float = 0.0
    mistral_temp_classification: float = 0.0
    mistral_temp_recommendation: float = 0.4
    mistral_temp_dialog: float = 0.5

    # DeepSeek API
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_max_tokens: int = 2048
    deepseek_temperature: float = 0.3

    # OpenRouter
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"
    openrouter_max_tokens: int = 1000
    openrouter_temperature: float = 0.7

    # GigaChat Credentials
    gigachat_credentials: SecretStr | None = None
    gigachat_llm_credentials: SecretStr | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_llm_scope: str | None = None
    gigachat_verify_ssl: bool = True

    # HTTP parsers SSL
    parser_ssl_verify: bool = True

    # Парсеры
    parser_irk_url: str = "https://irk.ru/afisha/"
    parser_culture38_url: str = "https://culture38.ru/"
    parser_timeout: int = 60
    parser_batch_size: int = 10

    # RAG
    rag_search_results: int = 5
    rag_index_batch_size: int = 10

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_default_ttl: int = 300

    # Security
    api_key: SecretStr | None = None
    rate_limit_requests: int = 60
    rate_limit_period: int = 60
    environment: Literal["development", "staging", "production"] = "development"

    @field_validator("rate_limit_requests", "rate_limit_period")
    @classmethod
    def _positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be positive")
        return v

    @field_validator("redis_port")
    @classmethod
    def _valid_port(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("port must be 1-65535")
        return v

    def get_api_key(self) -> str | None:
        """Безопасное получение API key."""
        return self.api_key.get_secret_value() if self.api_key else None

    def get_mistral_key(self) -> str | None:
        """Безопасное получение Mistral API key."""
        return self.mistral_api_key.get_secret_value() if self.mistral_api_key else None

    def get_gigachat_credentials(self) -> str | None:
        """Безопасное получение GigaChat credentials."""
        return self.gigachat_credentials.get_secret_value() if self.gigachat_credentials else None


settings = Settings()
