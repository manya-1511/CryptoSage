
"""
Pydantic schemas for CryptoSage.

These define the shape of data used for API request/response validation.
They mirror the SQLAlchemy models while allowing the database and API
layers to evolve independently.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FirmwareBase(BaseModel):
    """Fields shared when creating or reading a firmware record."""

    filename: str
    file_hash: str
    file_size: int
    architecture: str | None = None
    storage_path: str | None = None
    status: str | None = "Uploaded"


class FirmwareCreate(FirmwareBase):
    """Schema used when creating a new firmware record."""


class Firmware(FirmwareBase):
    """Schema used when returning a firmware record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_time: datetime


class FirmwareUploadResponse(BaseModel):
    """Response for a successful, brand-new firmware upload."""

    firmware_id: int
    filename: str
    file_hash: str
    file_size: int
    status: str


class FirmwareDuplicateResponse(BaseModel):
    """Response returned when a firmware hash already exists."""

    message: str = "Firmware already exists."
    firmware_id: int
    sha256: str
    status: str = "Already Uploaded"


class FirmwareAnalysisResult(BaseModel):
    """Summary for a single analyzed binary executable."""

    binary_name: str
    architecture: str | None = None
    binary_size: int | None = None
    feature_count: int
    feature_vector_path: str


class FirmwareAnalysisResponse(BaseModel):
    """Response returned after firmware analysis."""

    firmware_id: int
    status: str
    extraction_success: bool
    extraction_message: str
    binaries_discovered: int
    analyzed_binaries: list[FirmwareAnalysisResult]
    analysis_time_ms: float


class AnalysisBase(BaseModel):
    """Fields shared when creating or reading an analysis record."""

    firmware_id: int
    algorithm: str | None = None
    confidence: float | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    recommendation: list[Any] | None = None
    risk_factors: list[Any] | None = None
    analysis_status: str | None = None


class AnalysisCreate(AnalysisBase):
    """Schema used when creating a new analysis record."""


class Analysis(AnalysisBase):
    """Schema used when returning an analysis record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_time: datetime


class ReportBase(BaseModel):
    """Fields shared when creating or reading a report record."""

    analysis_id: int
    # JSONB normally stores a structured object. Accept strings as well
    # to avoid rejecting legacy records or existing string-based callers.
    rag_explanation: dict[str, Any] | str | None = None
    pdf_path: str | None = None


class ReportCreate(ReportBase):
    """Schema used when creating a new report record."""


class Report(ReportBase):
    """Schema used when returning a report record from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class UploadedFeaturesBase(BaseModel):
    """Fields shared when creating or reading extracted features."""

    firmware_id: int
    feature_vector: dict[str, Any] | None = None
    similarity_score: float | None = None


class UploadedFeaturesCreate(UploadedFeaturesBase):
    """Schema used when creating an uploaded-features record."""


class UploadedFeatures(UploadedFeaturesBase):
    """Schema used when returning an uploaded-features record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_time: datetime


class SinglePrediction(BaseModel):
    """Response for a firmware with exactly one analyzed executable."""

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
    """Prediction for one executable in a multi-binary response."""

    binary_name: str
    algorithm_family: str
    algorithm: str
    confidence: float
    prediction_time_ms: float


class MultiplePredictions(BaseModel):
    """Response for a firmware with multiple analyzed executables."""

    firmware_id: int
    model: str
    model_version: str
    predictions: list[BinaryPrediction]
    failed: list[dict[str, str]] = Field(default_factory=list)


class RiskFactorSchema(BaseModel):
    """One scored, evidence-backed contributor to a risk assessment."""

    factor: str
    weight: float
    contribution: float
    evidence: str


class RiskAssessmentResponse(BaseModel):
    """Response for a single binary's risk assessment."""

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
    """Response for risk assessments covering multiple executables."""

    firmware_id: int
    assessments: list[RiskAssessmentResponse]
    failed: list[dict[str, str]] = Field(default_factory=list)


class ExplanationResponse(BaseModel):
    """Response for a single binary's RAG explanation."""

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
    """Response for explanations covering multiple executables."""

    firmware_id: int
    explanations: list[ExplanationResponse]
    failed: list[dict[str, str]] = Field(default_factory=list)
