
"""
SQLAlchemy ORM models for CryptoSage.

Defines the core database tables used by the platform:
- Firmware: uploaded firmware images and their metadata.
- Analysis: static/ML analysis results.
- Report: explanations and PDF report metadata.
- UploadedFeatures: extracted feature vectors and similarity scores.
"""

from datetime import datetime, timezone
from typing import Any


from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint
from database import Base


class FirmwareStatus:
    """Canonical firmware lifecycle status values."""

    UPLOADED = "Uploaded"
    EXTRACTING = "Extracting"
    EXTRACTED = "Extracted"
    ANALYZING = "Analyzing"
    COMPLETED = "Completed"
    FAILED = "Failed"


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""
    return datetime.now(timezone.utc)


class Firmware(Base):
    """Represents a single uploaded firmware image."""

    __tablename__ = "firmware"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    architecture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default=FirmwareStatus.UPLOADED, nullable=False
    )

    analyses: Mapped[list["Analysis"]] = relationship(
        "Analysis",
        back_populates="firmware",
        cascade="all, delete-orphan",
    )

    uploaded_features: Mapped[list["UploadedFeatures"]] = relationship(
        "UploadedFeatures",
        back_populates="firmware",
        cascade="all, delete-orphan",
    )


class AnalysisStatus:
    """Canonical analysis-record status values."""

    COMPLETED = "Completed"
    FAILED = "Failed"


class Analysis(Base):
    """Represents the result of analyzing a firmware image."""

    __tablename__ = "analysis"
    
    __table_args__ = (
        UniqueConstraint(
            "firmware_id",
            "binary_key",
            name="uq_analysis_firmware_binary_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    firmware_id: Mapped[int] = mapped_column(
        ForeignKey("firmware.id"), nullable=False
    )
    binary_key: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    algorithm: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recommendation: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    risk_factors: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    analysis_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    analysis_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    firmware: Mapped["Firmware"] = relationship(
        "Firmware", back_populates="analyses"
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )


class Report(Base):
    """Represents a generated explanation and/or PDF report."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("analysis.id"), nullable=False
    )
    rag_explanation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    analysis: Mapped["Analysis"] = relationship(
        "Analysis", back_populates="reports"
    )


class UploadedFeatures(Base):
    """Stores extracted features for an uploaded firmware image."""

    __tablename__ = "uploaded_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    firmware_id: Mapped[int] = mapped_column(
        ForeignKey("firmware.id"), nullable=False
    )
    feature_vector: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    firmware: Mapped["Firmware"] = relationship(
        "Firmware", back_populates="uploaded_features"
    )
