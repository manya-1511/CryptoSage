import os
import uuid
import aiofiles
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import UploadFile

from app.core.config import settings
from app.models.firmware import Firmware, ExtractionResult, FirmwareStatus, ExtractionStatus
from app.schemas.firmware import FirmwareCreate, FirmwareUpdate
from app.services.validation import validate_firmware_file, compute_hashes
from app.services.extractor import run_extraction

logger = logging.getLogger(__name__)


async def save_upload_file(upload_file: UploadFile) -> Tuple[str, str, int]:
    """Save uploaded file to disk. Returns (saved_path, unique_filename, size)."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = Path(upload_file.filename or "firmware.bin").suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)
    size = 0
    async with aiofiles.open(file_path, "wb") as out:
        while chunk := await upload_file.read(65536):
            size += len(chunk)
            if size > settings.max_file_size_bytes:
                await out.close()
                os.remove(file_path)
                raise ValueError(f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB} MB")
            await out.write(chunk)
    return file_path, unique_name, size


async def create_firmware(
    db: AsyncSession,
    upload_file: UploadFile,
) -> Firmware:
    """Handle file upload, validate, and persist firmware record."""
    # 1. Save to disk
    file_path, unique_name, file_size = await save_upload_file(upload_file)

    # 2. Compute hashes
    sha256, md5 = compute_hashes(file_path)

    # 3. Validate
    ext = Path(upload_file.filename or "firmware.bin").suffix.lower()
    is_valid, error_msg, meta = validate_firmware_file(
        file_path, upload_file.filename or unique_name, file_size
    )

    status = FirmwareStatus.VALID if is_valid else FirmwareStatus.INVALID

    # 4. Persist
    firmware = Firmware(
        filename=unique_name,
        original_filename=upload_file.filename or unique_name,
        file_path=file_path,
        file_size=file_size,
        file_extension=ext,
        mime_type=meta.get("mime_type"),
        sha256_hash=sha256,
        md5_hash=md5,
        architecture=meta.get("architecture"),
        endianness=meta.get("endianness"),
        status=status,
        validation_error=error_msg,
    )
    db.add(firmware)
    await db.flush()
    await db.refresh(firmware)
    return firmware


async def get_firmware(db: AsyncSession, firmware_id: str) -> Optional[Firmware]:
    result = await db.execute(select(Firmware).where(Firmware.id == firmware_id))
    return result.scalar_one_or_none()


async def list_firmware(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> Tuple[List[Firmware], int]:
    offset = (page - 1) * page_size
    total_result = await db.execute(select(func.count()).select_from(Firmware))
    total = total_result.scalar_one()
    items_result = await db.execute(
        select(Firmware).order_by(Firmware.created_at.desc()).offset(offset).limit(page_size)
    )
    return list(items_result.scalars().all()), total


async def delete_firmware(db: AsyncSession, firmware_id: str) -> bool:
    firmware = await get_firmware(db, firmware_id)
    if not firmware:
        return False
    # Remove file from disk
    try:
        if os.path.exists(firmware.file_path):
            os.remove(firmware.file_path)
    except OSError as e:
        logger.warning(f"Could not delete file {firmware.file_path}: {e}")
    await db.delete(firmware)
    return True


async def trigger_extraction(db: AsyncSession, firmware_id: str) -> Optional[ExtractionResult]:
    """Create extraction record and kick off binwalk async extraction."""
    firmware = await get_firmware(db, firmware_id)
    if not firmware:
        return None
    if firmware.status == FirmwareStatus.INVALID:
        raise ValueError("Cannot extract invalid firmware")

    # Update firmware status
    firmware.status = FirmwareStatus.EXTRACTING

    extraction = ExtractionResult(
        firmware_id=firmware.id,
        status=ExtractionStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(extraction)
    await db.flush()
    await db.refresh(extraction)

    # Run extraction (async, but awaited here for simplicity in Phase 1)
    result_data = await run_extraction(
        str(firmware.id),
        firmware.file_path,
        settings.EXTRACT_DIR,
    )

    # Update extraction record
    extraction.status = ExtractionStatus(result_data["status"])
    extraction.extraction_path = result_data.get("extraction_path")
    extraction.error_message = result_data.get("error_message")
    extraction.scan_results = result_data.get("scan_results")
    extraction.file_tree = result_data.get("file_tree")
    extraction.component_summary = result_data.get("component_summary")
    extraction.total_files_extracted = result_data.get("total_files_extracted", 0)
    extraction.total_size_extracted = result_data.get("total_size_extracted", 0)
    extraction.duration_seconds = result_data.get("duration_seconds")
    extraction.completed_at = result_data.get("completed_at")

    # Update firmware status
    firmware.status = (
        FirmwareStatus.EXTRACTED
        if extraction.status == ExtractionStatus.COMPLETED
        else FirmwareStatus.FAILED
    )

    await db.flush()
    await db.refresh(extraction)
    return extraction


async def get_extraction(db: AsyncSession, extraction_id: str) -> Optional[ExtractionResult]:
    result = await db.execute(
        select(ExtractionResult).where(ExtractionResult.id == extraction_id)
    )
    return result.scalar_one_or_none()


async def get_extractions_for_firmware(
    db: AsyncSession, firmware_id: str
) -> List[ExtractionResult]:
    result = await db.execute(
        select(ExtractionResult)
        .where(ExtractionResult.firmware_id == firmware_id)
        .order_by(ExtractionResult.created_at.desc())
    )
    return list(result.scalars().all())