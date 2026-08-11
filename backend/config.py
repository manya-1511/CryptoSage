"""
Application configuration.

Loads all configurable values from environment variables so that no
credentials or secrets are ever hardcoded in source code.

A `.env` file (not committed to version control) can be used locally to
provide these values. See `.env.example` for the expected keys.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file into the process environment, if present.
load_dotenv()

# Root of the `backend/` package (this file's directory).
BASE_DIR: Path = Path(__file__).resolve().parent


class Settings:
    """Central place for all application settings.

    Values are read once from environment variables when the class is
    instantiated. Use the `get_settings()` function below to access a
    cached instance instead of creating this class directly.
    """

    # --- Database ---------------------------------------------------
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/cryptosage",
    )

    # --- Security -----------------------------------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")

    # --- Application behaviour ----------------------------------------
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    # --- Project metadata (used by the root endpoint) ------------------
    PROJECT_NAME: str = "CryptoSage"
    VERSION: str = "1.0"

    # --- Firmware upload (Phase 3) --------------------------------------
    # Directory where uploaded firmware files are stored, organized as
    # <UPLOAD_DIR>/<firmware_id>/<original_filename>.
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))

    # --- Firmware analysis (Phase 4) ------------------------------------
    # Directory where Binwalk extraction output is written, organized as
    # <ANALYSIS_OUTPUT_DIR>/<firmware_id>/.
    ANALYSIS_OUTPUT_DIR: Path = Path(
        os.getenv("ANALYSIS_OUTPUT_DIR", str(BASE_DIR / "analysis_output"))
    )

    # --- Machine learning (Phase 5A/5B) ----------------------------------
    # Directory holding the trained model and its supporting artifacts
    # (model_v1.pkl, label_encoder.pkl, feature_columns.json, etc.),
    # written by ml/train.py and read by ml/predict.py.
    ML_SAVED_MODELS_DIR: Path = Path(
        os.getenv("ML_SAVED_MODELS_DIR", str(BASE_DIR / "ml" / "saved_models"))
    )

    # Directory holding the dataset preprocessing metadata (categorical
    # encodings, numeric scaler parameters) produced by
    # dataset/preprocess.py, which ml/predict.py reuses at inference
    # time to derive the same encoded/normalized features the model was
    # trained on from a runtime feature vector.
    DATASET_PROCESSED_DIR: Path = Path(
        os.getenv("DATASET_PROCESSED_DIR", str(BASE_DIR / "dataset" / "data" / "processed"))
    )

    # --- Risk assessment & recommendations (Phase 6/7) -------------------
    # Configuration files driving ml/risk.py and ml/recommend.py. Every
    # weight, threshold, and recommendation string lives in these files
    # rather than in code, so new rules/algorithms/recommendations can
    # be added by editing configuration only.
    RISK_CONFIG_PATH: Path = Path(
        os.getenv("RISK_CONFIG_PATH", str(BASE_DIR / "ml" / "risk_config.json"))
    )
    RECOMMENDATION_RULES_PATH: Path = Path(
        os.getenv("RECOMMENDATION_RULES_PATH", str(BASE_DIR / "ml" / "recommendation_rules.json"))
    )

    # --- Explainable RAG engine (Phase 7) ---------------------------------
    RAG_KNOWLEDGE_BASE_DIR: Path = Path(
        os.getenv("RAG_KNOWLEDGE_BASE_DIR", str(BASE_DIR / "rag" / "knowledge_base"))
    )
    RAG_CHROMA_PERSIST_DIR: Path = Path(
        os.getenv("RAG_CHROMA_PERSIST_DIR", str(BASE_DIR / "rag" / "chroma_store"))
    )
    RAG_COLLECTION_NAME: str = os.getenv("RAG_COLLECTION_NAME", "cryptosage_knowledge_base")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "4"))
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    # Local LLM (Ollama). Never a paid/hosted API.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct-q4_0")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))

    # Maximum accepted upload size, in megabytes. Configurable via
    # MAX_UPLOAD_SIZE_MB so it never needs to be hardcoded in code.
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

    # File extensions accepted for firmware uploads. Configurable via a
    # comma-separated ALLOWED_FIRMWARE_EXTENSIONS environment variable
    # (e.g. "bin,img,elf"), never hardcoded into the validation logic.
    ALLOWED_FIRMWARE_EXTENSIONS: set[str] = {
        f".{ext.strip().lstrip('.').lower()}"
        for ext in os.getenv("ALLOWED_FIRMWARE_EXTENSIONS", "bin,img,elf").split(",")
        if ext.strip()
    }

    # MIME types accepted in addition to "unknown" (Python's `mimetypes`
    # module does not recognize firmware extensions like .bin/.img/.elf
    # and returns None for them, which is expected and accepted).
    ALLOWED_FIRMWARE_MIME_TYPES: set[str] = {
        mime.strip()
        for mime in os.getenv(
            "ALLOWED_FIRMWARE_MIME_TYPES",
            "application/octet-stream,application/x-executable,application/x-elf,application/x-object",
        ).split(",")
        if mime.strip()
    }

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum accepted upload size in bytes, derived from `MAX_UPLOAD_SIZE_MB`."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Using `lru_cache` ensures environment variables are read only once,
    avoiding repeated disk/environment lookups on every request.
    """
    return Settings()
