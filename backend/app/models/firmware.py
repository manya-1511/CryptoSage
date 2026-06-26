import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Float,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base

class FirmwareStatus(str, enum.Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


class ExtractionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Firmware(Base):
    __tablename__ = "firmwares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_extension = Column(String(10), nullable=False)
    mime_type = Column(String(128), nullable=True)
    sha256_hash = Column(String(64), nullable=True, index=True)
    md5_hash = Column(String(32), nullable=True)

    # Metadata
    architecture = Column(String(64), nullable=True)
    endianness = Column(String(16), nullable=True)
    description = Column(Text, nullable=True)
    vendor = Column(String(128), nullable=True)
    version = Column(String(64), nullable=True)

    # Status
    status = Column(
    SQLEnum(
        FirmwareStatus,
        values_callable=lambda obj: [e.value for e in obj],
    ),
    default=FirmwareStatus.PENDING,
    nullable=False,
)
    validation_error = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    extractions = relationship("ExtractionResult", back_populates="firmware", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Firmware(id={self.id}, filename={self.filename}, status={self.status})>"


class ExtractionResult(Base):
    __tablename__ = "extraction_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    firmware_id = Column(UUID(as_uuid=True), ForeignKey("firmwares.id", ondelete="CASCADE"), nullable=False)

    # Extraction metadata
    extraction_path = Column(String(512), nullable=True)
    tool_used = Column(String(64), default="binwalk", nullable=False)
    status = Column(
    SQLEnum(
        ExtractionStatus,
        values_callable=lambda obj: [e.value for e in obj],
    ),
    default=ExtractionStatus.PENDING,
    nullable=False,
)
    error_message = Column(Text, nullable=True)

    # Binwalk scan results
    scan_results = Column(JSON, nullable=True)        # Raw binwalk signatures
    file_tree = Column(JSON, nullable=True)           # Extracted file structure
    entropy_data = Column(JSON, nullable=True)        # Entropy analysis
    component_summary = Column(JSON, nullable=True)   # Detected components

    # Stats
    total_files_extracted = Column(Integer, default=0)
    total_size_extracted = Column(BigInteger, default=0)
    duration_seconds = Column(Float, nullable=True)

    # Timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    firmware = relationship("Firmware", back_populates="extractions")

    def __repr__(self):
        return f"<ExtractionResult(id={self.id}, firmware_id={self.firmware_id}, status={self.status})>"