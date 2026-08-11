"""
Pydantic schemas for CryptoSage.

These define the shape of data used for API request/response validation.
They mirror the SQLAlchemy models in `models.py` but are kept separate so
that the database layer and the API layer can evolve independently.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class FirmwareBase(BaseModel):
    """Fields shared when creating or reading a firmware record."""

    filename: str
    file_hash: str
    file_size: int
    architecture: Optional[str] = None
    storage_path: Optional[str] = None
    status: Optional[str] = "Uploaded"


class FirmwareCreate(FirmwareBase):
    """Schema used when creating a new firmware record."""
    pass


class Firmware(FirmwareBase):
    """Schema used when returning a firmware record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_time: datetime


class FirmwareUploadResponse(BaseModel):
    """Response returned after a successful, brand-new firmware upload."""

    firmware_id: int
    filename: str
    file_hash: str
    file_size: int
    status: str


class FirmwareDuplicateResponse(BaseModel):
    """Response returned when an uploaded firmware's SHA-256 already exists."""

    message: str = "Firmware already exists."
    firmware_id: int
    sha256: str
    status: str = "Already Uploaded"


class AnalysisBase(BaseModel):
    """Fields shared when creating or reading an analysis record."""

    firmware_id: int
    algorithm: Optional[str] = None
    confidence: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    recommendation: Optional[str] = None


class AnalysisCreate(AnalysisBase):
    """Schema used when creating a new analysis record."""
    pass


class Analysis(AnalysisBase):
    """Schema used when returning an analysis record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_time: datetime


class ReportBase(BaseModel):
    """Fields shared when creating or reading a report record."""

    analysis_id: int
    rag_explanation: Optional[str] = None
    pdf_path: Optional[str] = None


class ReportCreate(ReportBase):
    """Schema used when creating a new report record."""
    pass


class Report(ReportBase):
    """Schema used when returning a report record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UploadedFeaturesBase(BaseModel):
    """Fields shared when creating or reading an uploaded-features record."""

    firmware_id: int
    feature_vector: Optional[dict[str, Any]] = None
    similarity_score: Optional[float] = None


class UploadedFeaturesCreate(UploadedFeaturesBase):
    """Schema used when creating a new uploaded-features record."""
    pass


class UploadedFeatures(UploadedFeaturesBase):
    """Schema used when returning an uploaded-features record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_time: datetime


class SinglePrediction(BaseModel):
    """Response for a firmware with exactly one analyzed executable (Phase 6)."""

    firmware_id: int
    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    model: str
    model_version: str
    prediction_time_ms: float
    feature_count_used: int


class BinaryPrediction(BaseModel):
    """One executable's prediction within a multi-binary response (Phase 6)."""

    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    prediction_time_ms: float


class MultiplePredictions(BaseModel):
    """Response for a firmware with multiple analyzed executables (Phase 6)."""

    firmware_id: int
    model: str
    model_version: str
    predictions: list[BinaryPrediction]
    failed: list[dict[str, str]] = []


class RiskFactorSchema(BaseModel):
    """One scored, evidence-backed contributor to a risk assessment (Phase 6/7)."""

    factor: str
    weight: float
    contribution: float
    evidence: str


class RiskAssessmentResponse(BaseModel):
    """Response for a single binary's risk assessment (Phase 6/7)."""

    firmware_id: int
    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    risk_score: float
    risk_level: str
    risk_factors: list[str]
    recommendations: list[str]


class MultipleRiskAssessments(BaseModel):
    """Response for a firmware with multiple assessed executables (Phase 6/7)."""

    firmware_id: int
    assessments: list[RiskAssessmentResponse]
    failed: list[dict[str, str]] = []


class ExplanationResponse(BaseModel):
    """Response for a single binary's evidence-backed RAG explanation (Phase 7)."""

    firmware_id: int
    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    risk_score: float
    risk_level: str
    summary: str
    sections: dict[str, str]
    recommendations: list[str]
    references: list[str]
    generated_by: str
    generation_time_ms: float


class MultipleExplanations(BaseModel):
    """Response for a firmware with multiple explained executables (Phase 7)."""

    firmware_id: int
    explanations: list[ExplanationResponse]
    failed: list[dict[str, str]] = []
