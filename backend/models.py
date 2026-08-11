"""
SQLAlchemy ORM models for CryptoSage.

Defines the core database tables used by the platform:

- `Firmware`: uploaded firmware images and their metadata.
- `Analysis`: results of static/ML analysis performed on a firmware image.
- `Report`: generated explanations and PDF reports tied to an analysis.
- `UploadedFeatures`: extracted feature vectors and similarity scores
  captured for an uploaded firmware image (used by the online analysis
  pipeline to compare against the offline reference dataset).
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class FirmwareStatus:
    """Canonical firmware lifecycle status values.

    Only `UPLOADED` is ever set during Phase 3 (Firmware Input Module).
    The remaining statuses are defined now so later phases (extraction,
    analysis, reporting) can reuse the same vocabulary without a schema
    change.
    """

    UPLOADED = "Uploaded"
    EXTRACTING = "Extracting"
    EXTRACTED = "Extracted"
    ANALYZING = "Analyzing"
    COMPLETED = "Completed"
    FAILED = "Failed"


def _utc_now() -> datetime:
    """Return the current UTC time. Used as a default for timestamp columns."""
    return datetime.now(timezone.utc)


class Firmware(Base):
    """Represents a single uploaded firmware image."""

    __tablename__ = "firmware"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    architecture: Mapped[str] = mapped_column(String(50), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    status: Mapped[str] = mapped_column(String(50), default=FirmwareStatus.UPLOADED)

    # One firmware image can have many analyses performed on it over time.
    analyses: Mapped[list["Analysis"]] = relationship(
        "Analysis", back_populates="firmware", cascade="all, delete-orphan"
    )

    # One firmware image can have many extracted feature records over time.
    uploaded_features: Mapped[list["UploadedFeatures"]] = relationship(
        "UploadedFeatures", back_populates="firmware", cascade="all, delete-orphan"
    )


class AnalysisStatus:
    """Canonical analysis-record status values (Phase 6/7).

    Set by the risk-assessment workflow to reflect how far a given
    `analysis` row got, independent of the firmware's own upload-level
    `FirmwareStatus`.
    """

    COMPLETED = "Completed"
    FAILED = "Failed"


class Analysis(Base):
    """Represents the result of analyzing a firmware image."""

    __tablename__ = "analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    firmware_id: Mapped[int] = mapped_column(ForeignKey("firmware.id"), nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=True)
    recommendation: Mapped[list] = mapped_column(JSONB, nullable=True)
    risk_factors: Mapped[list] = mapped_column(JSONB, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(50), nullable=True)
    analysis_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Many analyses belong to one firmware image.
    firmware: Mapped["Firmware"] = relationship("Firmware", back_populates="analyses")

    # One analysis can produce many reports (e.g. re-generated later).
    reports: Mapped[list["Report"]] = relationship(
        "Report", back_populates="analysis", cascade="all, delete-orphan"
    )


class Report(Base):
    """Represents a generated report (RAG explanation + PDF) for an analysis."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis.id"), nullable=False)
    rag_explanation: Mapped[dict] = mapped_column(JSONB, nullable=True)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Many reports belong to one analysis.
    analysis: Mapped["Analysis"] = relationship("Analysis", back_populates="reports")


class UploadedFeatures(Base):
    """Represents an extracted feature vector for an uploaded firmware image.

    Stores the static-analysis feature vector produced by the online
    analysis pipeline (see `analysis/features.py`) along with the
    similarity score computed against the offline reference dataset
    (see `analysis/similarity.py`).
    """

    __tablename__ = "uploaded_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    firmware_id: Mapped[int] = mapped_column(ForeignKey("firmware.id"), nullable=False)
    feature_vector: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=True)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)

    # Many feature records belong to one firmware image.
    firmware: Mapped["Firmware"] = relationship("Firmware", back_populates="uploaded_features")
