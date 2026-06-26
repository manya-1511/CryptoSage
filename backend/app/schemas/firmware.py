from pydantic import BaseModel, Field, UUID4
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models.firmware import FirmwareStatus, ExtractionStatus


# ─── Firmware Schemas ────────────────────────────────────────────────────────

class FirmwareBase(BaseModel):
    original_filename: str
    file_size: int
    file_extension: str
    mime_type: Optional[str] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    version: Optional[str] = None


class FirmwareCreate(FirmwareBase):
    filename: str
    file_path: str
    sha256_hash: Optional[str] = None
    md5_hash: Optional[str] = None


class FirmwareUpdate(BaseModel):
    status: Optional[FirmwareStatus] = None
    description: Optional[str] = None
    vendor: Optional[str] = None
    version: Optional[str] = None
    architecture: Optional[str] = None
    endianness: Optional[str] = None
    validation_error: Optional[str] = None


class FirmwareResponse(FirmwareBase):
    id: UUID4
    filename: str
    sha256_hash: Optional[str] = None
    md5_hash: Optional[str] = None
    architecture: Optional[str] = None
    endianness: Optional[str] = None
    status: FirmwareStatus
    validation_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FirmwareListResponse(BaseModel):
    items: List[FirmwareResponse]
    total: int
    page: int
    page_size: int


# ─── Extraction Schemas ───────────────────────────────────────────────────────

class BinwalkSignature(BaseModel):
    offset: int
    hex_offset: str
    description: str
    name: Optional[str] = None


class FileTreeNode(BaseModel):
    name: str
    path: str
    type: str  # "file" | "directory"
    size: Optional[int] = None
    children: Optional[List["FileTreeNode"]] = None

    model_config = {"from_attributes": True}


FileTreeNode.model_rebuild()


class ExtractionResultCreate(BaseModel):
    firmware_id: UUID4
    tool_used: str = "binwalk"


class ExtractionResultResponse(BaseModel):
    id: UUID4
    firmware_id: UUID4
    extraction_path: Optional[str] = None
    tool_used: str
    status: ExtractionStatus
    error_message: Optional[str] = None
    scan_results: Optional[List[Dict[str, Any]]] = None
    file_tree: Optional[Dict[str, Any]] = None
    entropy_data: Optional[List[Dict[str, Any]]] = None
    component_summary: Optional[Dict[str, Any]] = None
    total_files_extracted: int
    total_size_extracted: int
    duration_seconds: Optional[float] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Upload Response ──────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    firmware: FirmwareResponse
    message: str
    validation_passed: bool


class ExtractionTriggerResponse(BaseModel):
    extraction_id: UUID4
    firmware_id: UUID4
    message: str
    status: ExtractionStatus