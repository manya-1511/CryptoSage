
"""
Application configuration.

Loads configurable values from environment variables. Use a local .env file
for development and environment variables/secrets for production.

Production settings are validated when get_settings() is first called.
"""

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean environment variable without silently accepting typos."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False

    raise ValueError(f"{name} must be a boolean value.")


def _env_int(name: str, default: int) -> int:
    """Read an integer environment variable with a useful error message."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _env_float(name: str, default: float) -> float:
    """Read a floating-point environment variable with a useful error message."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return float(value.strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc


def _env_csv_set(name: str, default: str) -> set[str]:
    """Read a comma-separated environment variable into a normalized set."""
    return {
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    }


class Settings:
    """Centralized application settings."""

    # --- Environment and deployment ---------------------------------
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    DEBUG: bool = _env_bool("DEBUG", True)

    # --- Database ----------------------------------------------------
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/cryptosage",
    )
    DB_POOL_SIZE: int = _env_int("DB_POOL_SIZE", 5)
    DB_MAX_OVERFLOW: int = _env_int("DB_MAX_OVERFLOW", 10)
    DB_POOL_TIMEOUT_SECONDS: int = _env_int("DB_POOL_TIMEOUT_SECONDS", 30)
    DB_POOL_RECYCLE_SECONDS: int = _env_int("DB_POOL_RECYCLE_SECONDS", 1800)

    # --- Security ----------------------------------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")

    # --- CORS --------------------------------------------------------
    # Comma-separated origins, e.g.
    # CORS_ORIGINS=https://cryptosage.example.com,https://www.example.com
    CORS_ORIGINS: list[str] = [
        origin.strip().rstrip("/")
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]

    # --- Project metadata -------------------------------------------
    PROJECT_NAME: str = "CryptoSage"
    VERSION: str = "1.0"

    # --- Firmware upload --------------------------------------------
    UPLOAD_DIR: Path = Path(
        os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
    )
    MAX_UPLOAD_SIZE_MB: int = _env_int("MAX_UPLOAD_SIZE_MB", 500)
    ALLOWED_FIRMWARE_EXTENSIONS: set[str] = {
        f".{ext.strip().lstrip('.').lower()}"
        for ext in os.getenv(
            "ALLOWED_FIRMWARE_EXTENSIONS", "bin,img,elf"
        ).split(",")
        if ext.strip()
    }
    ALLOWED_FIRMWARE_MIME_TYPES: set[str] = _env_csv_set(
        "ALLOWED_FIRMWARE_MIME_TYPES",
        (
            "application/octet-stream,application/x-executable,"
            "application/x-elf,application/x-object"
        ),
    )

    # --- Firmware analysis ------------------------------------------
    ANALYSIS_OUTPUT_DIR: Path = Path(
        os.getenv("ANALYSIS_OUTPUT_DIR", str(BASE_DIR / "analysis_output"))
    )

    # --- Machine learning -------------------------------------------
    ML_SAVED_MODELS_DIR: Path = Path(
        os.getenv("ML_SAVED_MODELS_DIR", str(BASE_DIR / "ml" / "saved_models"))
    )
    DATASET_PROCESSED_DIR: Path = Path(
        os.getenv(
            "DATASET_PROCESSED_DIR",
            str(BASE_DIR / "dataset" / "data" / "processed"),
        )
    )

    # --- Risk assessment and recommendations ------------------------
    RISK_CONFIG_PATH: Path = Path(
        os.getenv("RISK_CONFIG_PATH", str(BASE_DIR / "ml" / "risk_config.json"))
    )
    RECOMMENDATION_RULES_PATH: Path = Path(
        os.getenv(
            "RECOMMENDATION_RULES_PATH",
            str(BASE_DIR / "ml" / "recommendation_rules.json"),
        )
    )

    # --- RAG ---------------------------------------------------------
    RAG_KNOWLEDGE_BASE_DIR: Path = Path(
        os.getenv("RAG_KNOWLEDGE_BASE_DIR", str(BASE_DIR / "rag" / "knowledge_base"))
    )
    RAG_CHROMA_PERSIST_DIR: Path = Path(
        os.getenv("RAG_CHROMA_PERSIST_DIR", str(BASE_DIR / "rag" / "chroma_store"))
    )
    RAG_COLLECTION_NAME: str = os.getenv(
        "RAG_COLLECTION_NAME", "cryptosage_knowledge_base"
    )
    RAG_TOP_K: int = _env_int("RAG_TOP_K", 5)
    RAG_CANDIDATE_K: int = _env_int("RAG_CANDIDATE_K", 8)

    RAG_RERANK_WEIGHT_SEMANTIC: float = _env_float(
        "RAG_RERANK_WEIGHT_SEMANTIC", 0.60
    )
    RAG_RERANK_WEIGHT_ALGORITHM: float = _env_float(
        "RAG_RERANK_WEIGHT_ALGORITHM", 0.20
    )
    RAG_RERANK_WEIGHT_RISK_FACTOR: float = _env_float(
        "RAG_RERANK_WEIGHT_RISK_FACTOR", 0.10
    )
    RAG_RERANK_WEIGHT_METADATA: float = _env_float(
        "RAG_RERANK_WEIGHT_METADATA", 0.10
    )
    RAG_EMBEDDING_MODEL: str = os.getenv(
        "RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
    )

    # --- Local LLM: Ollama ------------------------------------------
    OLLAMA_BASE_URL: str = os.getenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    ).rstrip("/")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    OLLAMA_TIMEOUT_SECONDS: int = _env_int("OLLAMA_TIMEOUT_SECONDS", 180)

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def validate(self) -> None:
        """Validate settings that could cause unsafe or invalid operation."""
        if self.ENVIRONMENT not in {"development", "testing", "production"}:
            raise ValueError(
                "ENVIRONMENT must be development, testing, or production."
            )

        if self.MAX_UPLOAD_SIZE_MB <= 0:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be greater than zero.")

        if not self.ALLOWED_FIRMWARE_EXTENSIONS:
            raise ValueError("ALLOWED_FIRMWARE_EXTENSIONS cannot be empty.")

        if self.DB_POOL_SIZE < 1:
            raise ValueError("DB_POOL_SIZE must be at least 1.")
        if self.DB_MAX_OVERFLOW < 0:
            raise ValueError("DB_MAX_OVERFLOW cannot be negative.")
        if self.DB_POOL_TIMEOUT_SECONDS < 1:
            raise ValueError("DB_POOL_TIMEOUT_SECONDS must be positive.")
        if self.DB_POOL_RECYCLE_SECONDS < 1:
            raise ValueError("DB_POOL_RECYCLE_SECONDS must be positive.")

        if self.RAG_TOP_K < 1:
            raise ValueError("RAG_TOP_K must be at least 1.")
        if self.RAG_CANDIDATE_K < self.RAG_TOP_K:
            raise ValueError("RAG_CANDIDATE_K must be greater than or equal to RAG_TOP_K.")
        if self.OLLAMA_TIMEOUT_SECONDS < 1:
            raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive.")

        weights = (
            self.RAG_RERANK_WEIGHT_SEMANTIC,
            self.RAG_RERANK_WEIGHT_ALGORITHM,
            self.RAG_RERANK_WEIGHT_RISK_FACTOR,
            self.RAG_RERANK_WEIGHT_METADATA,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("RAG reranker weights cannot be negative.")
        if abs(sum(weights) - 1.0) > 0.05:
            raise ValueError("RAG reranker weights must sum to approximately 1.0.")

        if not self.RAG_COLLECTION_NAME.strip():
            raise ValueError("RAG_COLLECTION_NAME cannot be empty.")
        if not self.RAG_EMBEDDING_MODEL.strip():
            raise ValueError("RAG_EMBEDDING_MODEL cannot be empty.")
        if not self.OLLAMA_MODEL.strip():
            raise ValueError("OLLAMA_MODEL cannot be empty.")

        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production.")
            if (
                not self.SECRET_KEY
                or self.SECRET_KEY == "change-me-in-production"
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError(
                    "Production requires a SECRET_KEY of at least 32 characters "
                    "that is not the development placeholder."
                )
            if self.DATABASE_URL.startswith(
                "postgresql://postgres:postgres@localhost"
            ):
                raise ValueError(
                    "Production DATABASE_URL must be configured with deployment credentials."
                )
            if not self.CORS_ORIGINS:
                raise ValueError(
                    "Set CORS_ORIGINS to the trusted frontend origin(s) in production."
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError(
                    "Wildcard CORS origins are not allowed in production."
                )

        for origin in self.CORS_ORIGINS:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    f"Invalid CORS origin {origin!r}; provide a full http(s) origin."
                )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the validated, cached settings instance."""
    settings = Settings()
    settings.validate()
    return settings
