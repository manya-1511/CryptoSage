import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.firmware import (
    ExtractionResultResponse,
    ExtractionTriggerResponse,
    FirmwareListResponse,
    FirmwareResponse,
    UploadResponse,
)
from app.services.firmware_service import (
    create_firmware,
    delete_firmware,
    get_extraction,
    get_extractions_for_firmware,
    get_firmware,
    list_firmware,
    trigger_extraction,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/firmware", tags=["Firmware"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_firmware(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a firmware file (.bin, .img, .elf, .hex). Validates and stores metadata."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        firmware = await create_firmware(db, file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Firmware upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    return UploadResponse(
        firmware=FirmwareResponse.model_validate(firmware),
        message="Firmware uploaded successfully" if firmware.validation_error is None else f"Uploaded with warning: {firmware.validation_error}",
        validation_passed=firmware.validation_error is None,
    )


@router.get("", response_model=FirmwareListResponse)
async def list_all_firmware(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded firmware with pagination."""
    items, total = await list_firmware(db, page=page, page_size=page_size)
    return FirmwareListResponse(
        items=[FirmwareResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{firmware_id}", response_model=FirmwareResponse)
async def get_firmware_by_id(
    firmware_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get firmware details by ID."""
    firmware = await get_firmware(db, str(firmware_id))
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware not found")
    return FirmwareResponse.model_validate(firmware)


@router.delete("/{firmware_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_firmware(
    firmware_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete firmware and its file from disk."""
    deleted = await delete_firmware(db, str(firmware_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Firmware not found")


@router.post("/{firmware_id}/extract", response_model=ExtractionTriggerResponse)
async def extract_firmware(
    firmware_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger binwalk extraction for a firmware file."""
    try:
        extraction = await trigger_extraction(db, str(firmware_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

    if not extraction:
        raise HTTPException(status_code=404, detail="Firmware not found")

    return ExtractionTriggerResponse(
        extraction_id=extraction.id,
        firmware_id=extraction.firmware_id,
        message=f"Extraction {extraction.status.value}",
        status=extraction.status,
    )


@router.get("/{firmware_id}/extractions", response_model=list[ExtractionResultResponse])
async def list_extractions(
    firmware_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all extraction results for a firmware."""
    firmware = await get_firmware(db, str(firmware_id))
    if not firmware:
        raise HTTPException(status_code=404, detail="Firmware not found")
    extractions = await get_extractions_for_firmware(db, str(firmware_id))
    return [ExtractionResultResponse.model_validate(e) for e in extractions]


@router.get("/{firmware_id}/extractions/{extraction_id}", response_model=ExtractionResultResponse)
async def get_extraction_detail(
    firmware_id: UUID,
    extraction_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed extraction result including file tree and scan signatures."""
    extraction = await get_extraction(db, str(extraction_id))
    if not extraction or str(extraction.firmware_id) != str(firmware_id):
        raise HTTPException(status_code=404, detail="Extraction not found")
    return ExtractionResultResponse.model_validate(extraction)