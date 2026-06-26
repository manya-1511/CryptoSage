from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "CryptoSage"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql://cryptosage:cryptosage_secret@localhost:5432/cryptosage_db"

    UPLOAD_DIR: str = "./uploads"
    EXTRACT_DIR: str = "./extractions"
    MAX_FILE_SIZE_MB: int = 512

    CORS_ORIGINS: str = "http://localhost:3000"

    SUPPORTED_EXTENSIONS: List[str] = [".bin", ".img", ".elf", ".hex"]
    SUPPORTED_MIME_TYPES: List[str] = [
        "application/octet-stream",
        "application/x-executable",
        "application/x-elf",
        "application/x-object",
        "application/x-sharedlib",
        "application/x-firmware",
        "application/x-raw-disk-image",
        "application/x-hex",
        "application/x-ihex",
        "text/plain",
    ]

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"


settings = Settings()