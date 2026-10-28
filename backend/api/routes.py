 
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analysis.binary import parse_elf
from analysis.pipeline import run_firmware_analysis
from config import get_settings
from database import SessionLocal, get_db
from input.upload import handle_firmware_upload
from ml.predict import (
    ModelLoadError,
    PredictionResult,
    PredictionValidationError,
    load_feature_vectors_for_firmware,
    predict_batch,
)
from ml.recommend import RecommendationConfigError, generate_recommendations
from ml.risk import RiskAssessment, RiskConfigError, assess_risk
from models import Analysis, AnalysisStatus, Firmware, Report
from rag.explain import ExplanationError, ExplanationResult, explain_firmware
from rag.retriever import RetrieverError
from schemas import Firmware as FirmwareSchema
from schemas import (
    BinaryPrediction,
    ExplanationResponse,
    FirmwareAnalysisResponse,
    FirmwareDuplicateResponse,
    FirmwareUploadResponse,
    MultipleExplanations,
    MultiplePredictions,
    MultipleRiskAssessments,
    RiskAssessmentResponse,
    SinglePrediction,
)

logger = logging.getLogger("cryptosage.api.routes")

router = APIRouter()
settings = get_settings()


@router.get("/")
def read_root() -> dict:
    """Return basic project information."""
    return {
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "Running",
    }


@router.get("/health")
def health_check() -> dict:
    """Check that the API and database connection are healthy."""
    db_status = "ok"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok",
        "database": db_status,
    }


@router.post(
    "/firmware/upload",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Upload a firmware file for intake",
)
def upload_firmware(
    file: UploadFile = File(..., description="Firmware image (.bin, .img, or .elf)"),
    db: Session = Depends(get_db),
) -> FirmwareUploadResponse | FirmwareDuplicateResponse:
    """Accept a firmware upload, validate it, and record it in the database.

    Validates the file's extension, MIME type, and size; streams it to
    disk while computing its SHA-256 hash; checks for a duplicate by
    hash; and, for a new firmware, stores it under
    `uploads/<firmware_id>/<original_filename>` and records its metadata.

    This endpoint does not extract, analyze, or otherwise inspect the
    firmware's contents -- see later phases for that functionality.
    """
    try:
        return handle_firmware_upload(file, db)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while handling firmware upload.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the upload.",
        )


@router.get(
    "/firmware",
    response_model=list[FirmwareSchema],
    summary="List all uploaded firmware records",
)
def list_firmware(db: Session = Depends(get_db)) -> list[Firmware]:
    """Return metadata for every uploaded firmware record, most recent first."""
    return db.query(Firmware).order_by(Firmware.upload_time.desc()).all()


@router.get(
    "/firmware/{firmware_id}",
    response_model=FirmwareSchema,
    summary="Get metadata for a single firmware record",
)
def get_firmware(firmware_id: int, db: Session = Depends(get_db)) -> Firmware:
    """Return metadata for one uploaded firmware record by its ID."""
    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if firmware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with id {firmware_id} was not found.",
        )
    return firmware


@router.post(
    "/analyze/{firmware_id}",
    response_model=FirmwareAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Run firmware extraction and static feature analysis",
)
@router.post(
    "/firmware/{firmware_id}/analyze",
    response_model=FirmwareAnalysisResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def analyze_firmware_endpoint(
    firmware_id: int, db: Session = Depends(get_db)
) -> FirmwareAnalysisResponse:
    """Extract a firmware image with Binwalk, discover ELF binaries,
    extract static features for each discovered binary, save feature vector
    JSON files for downstream ML prediction/risk/explain endpoints, and store
    the feature records in the database.
    """
    try:
        return run_firmware_analysis(firmware_id, db)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while analyzing firmware_id=%d", firmware_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while analyzing the firmware.",
        )


def _get_or_create_analysis(
    db: Session,
    firmware_id: int,
    prediction: PredictionResult,
) -> Analysis:
    """Return the canonical analysis row for one firmware binary."""
    binary_key = prediction.binary_key or prediction.binary_name

    analysis_row = (
        db.query(Analysis)
        .filter(
            Analysis.firmware_id == firmware_id,
            Analysis.binary_key == binary_key,
        )
        .one_or_none()
    )

    if analysis_row is None:
        analysis_row = Analysis(
            firmware_id=firmware_id,
            binary_key=binary_key,
            algorithm=prediction.algorithm,
            confidence=prediction.confidence,
        )
        db.add(analysis_row)

    return analysis_row

def _store_prediction(
    db: Session,
    firmware_id: int,
    prediction: PredictionResult,
) -> Analysis:
    """Update the canonical row with the latest ML prediction."""
    analysis_row = _get_or_create_analysis(db, firmware_id, prediction)
    analysis_row.algorithm = prediction.algorithm
    analysis_row.confidence = prediction.confidence
    return analysis_row


@router.post(
    "/predict/{firmware_id}",
    response_model=None,
    summary="Run ML inference on an already-analyzed firmware's executables",
)
def predict_firmware(
    firmware_id: int, db: Session = Depends(get_db)
) -> SinglePrediction | MultiplePredictions:
    """Predict the cryptographic algorithm for every analyzed executable
    inside an already-uploaded, already-analyzed firmware.

    Expects the Firmware Analysis Engine (Phase 4) to have already
    produced `feature_vector.json` file(s) for this firmware under
    `ANALYSIS_OUTPUT_DIR/<firmware_id>/`. This endpoint does not upload
    firmware, run Binwalk, or extract features -- it only loads
    existing feature vectors, runs the trained model, stores the
    result in the `analysis` table, and returns it.
    """
    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if firmware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with id {firmware_id} was not found.",
        )

    try:
        feature_vectors = load_feature_vectors_for_firmware(firmware_id, settings.ANALYSIS_OUTPUT_DIR)
    except Exception:
        logger.exception("Unexpected error while locating feature vectors for firmware_id=%d", firmware_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while locating analysis results.",
        )

    if not feature_vectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No analysis results found for this firmware. Run the Firmware "
                "Analysis Engine before requesting a prediction."
            ),
        )

    try:
        results, failures = predict_batch(feature_vectors)
    except ModelLoadError as exc:
        logger.error("Model artifacts could not be loaded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The prediction model is not currently available.",
        )
    except Exception:
        logger.exception("Unexpected error during prediction for firmware_id=%d", firmware_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating predictions.",
        )

    if not results:
        # Every binary failed validation/inference (e.g. every feature
        # vector had an invalid schema) -- a meaningful error, not a
        # silent empty success.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "No valid predictions could be generated.", "failures": failures},
        )

    try:
        for result in results:
            _store_prediction(db, firmware_id, result)

        db.commit()

    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to persist predictions for firmware_id=%d",
            firmware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save prediction results.",
        )
    if len(results) == 1 and not failures:
        result = results[0]
        return SinglePrediction(
            firmware_id=firmware_id,
            binary_name=result.binary_name,
            algorithm_family=result.algorithm_family,
            algorithm=result.algorithm,
            confidence=result.confidence,
            model=result.model,
            model_version=result.model_version,
            prediction_time_ms=result.prediction_time_ms,
            feature_count_used=result.feature_count_used,
        )

    return MultiplePredictions(
        firmware_id=firmware_id,
        model=results[0].model,
        model_version=results[0].model_version,
        predictions=[
            BinaryPrediction(
                binary_name=result.binary_name,
                algorithm_family=result.algorithm_family,
                algorithm=result.algorithm,
                confidence=result.confidence,
                prediction_time_ms=result.prediction_time_ms,
            )
            for result in results
        ],
        failed=failures,
    )


def _find_binary_path(analysis_output_dir: Path, firmware_id: int, binary_name: str) -> Optional[Path]:
    """Best-effort search for the original analyzed binary on disk.

    `feature_vector.json` files don't carry the original binary's path,
    only its name, so this searches the firmware's analysis output
    directory for a matching filename. Returns None (never raises) if
    it can't be found -- the binary-security factors that need richer
    ELF metadata simply degrade gracefully in that case.
    """
    firmware_dir = analysis_output_dir / str(firmware_id)
    if not firmware_dir.exists():
        return None
    for candidate in firmware_dir.rglob(binary_name):
        if candidate.is_file() and not candidate.name.endswith("_feature_vector.json"):
            return candidate
    return None


def _store_risk_assessment(
    db: Session,
    firmware_id: int,
    prediction: PredictionResult,
    risk_assessment: RiskAssessment,
    recommendations: list[str],
) -> Analysis:
    """Update the canonical row with risk and recommendation data."""
    analysis_row = _get_or_create_analysis(db, firmware_id, prediction)

    analysis_row.algorithm = prediction.algorithm
    analysis_row.confidence = prediction.confidence
    analysis_row.risk_score = risk_assessment.risk_score
    analysis_row.risk_level = risk_assessment.risk_level
    analysis_row.recommendation = recommendations
    analysis_row.risk_factors = [
        {
            "factor": factor.factor,
            "category": factor.category,
            "weight": factor.weight,
            "contribution": factor.contribution,
            "evidence": factor.evidence,
        }
        for factor in risk_assessment.risk_factors
        if factor.contribution > 0
    ]
    analysis_row.analysis_status = AnalysisStatus.COMPLETED

    return analysis_row






@router.post(
    "/risk/{firmware_id}",
    response_model=None,
    summary="Run ML prediction, risk assessment, and recommendations for a firmware",
)
def assess_firmware_risk(
    firmware_id: int,
    db: Session = Depends(get_db),
) -> RiskAssessmentResponse | MultipleRiskAssessments:
    """Run prediction, deterministic risk assessment, and recommendations.

    Feature vectors must already exist under ANALYSIS_OUTPUT_DIR/<firmware_id>/.
    This endpoint does not upload or extract firmware.
    """
    if firmware_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="firmware_id must be a positive integer.",
        )

    firmware = (
        db.query(Firmware)
        .filter(Firmware.id == firmware_id)
        .first()
    )
    if firmware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with id {firmware_id} was not found.",
        )

    try:
        feature_vectors = load_feature_vectors_for_firmware(
            firmware_id,
            settings.ANALYSIS_OUTPUT_DIR,
        )
    except Exception:
        logger.exception(
            "Failed to load feature vectors for firmware_id=%d",
            firmware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while locating analysis results.",
        )

    if not feature_vectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No analysis results found for this firmware. Run the "
                "Firmware Analysis Engine before requesting a risk assessment."
            ),
        )

    try:
        predictions, prediction_failures = predict_batch(feature_vectors)
    except ModelLoadError:
        logger.exception(
            "Prediction model unavailable for firmware_id=%d",
            firmware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The prediction model is not currently available.",
        )
    except Exception:
        logger.exception(
            "Unexpected prediction error for firmware_id=%d",
            firmware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating predictions.",
        )

    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "No valid predictions could be generated.",
                "failures": prediction_failures,
            },
        )

    feature_vectors_by_key = {
        str(features.get("_binary_key") or binary_name): features
        for binary_name, features in feature_vectors
    }

    firmware_age_days = (
        (datetime.now(timezone.utc) - firmware.upload_time).days
        if firmware.upload_time
        else None
    )
    firmware_metadata = {"age_days": firmware_age_days}

    assessments: list[RiskAssessmentResponse] = []
    failures = list(prediction_failures)

    for prediction in predictions:
        binary_key = prediction.binary_key or prediction.binary_name
        raw_feature_vector = feature_vectors_by_key.get(binary_key, {})

        binary_path = (
            settings.ANALYSIS_OUTPUT_DIR
            / str(firmware_id)
            / binary_key
        )
        binary_path = binary_path if binary_path.is_file() else None

        try:
            binary_metadata = (
                parse_elf(binary_path)
                if binary_path is not None
                else None
            )

            risk_assessment = assess_risk(
                firmware_id=firmware_id,
                algorithm=prediction.algorithm,
                algorithm_family=prediction.algorithm_family,
                confidence=prediction.confidence,
                feature_vector=raw_feature_vector,
                binary_metadata=binary_metadata,
                firmware_metadata=firmware_metadata,
            )

            recommendations = generate_recommendations(
                risk_assessment.risk_factors,
                prediction.algorithm,
            )

        except (RiskConfigError, RecommendationConfigError):
            logger.exception(
                "Risk/recommendation configuration error for binary '%s'",
                prediction.binary_name,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Risk assessment configuration is invalid or unavailable.",
            )
        except ValueError as exc:
            logger.warning(
                "Invalid risk assessment input for binary '%s': %s",
                prediction.binary_name,
                exc,
            )
            failures.append(
                {
                    "binary_name": prediction.binary_name,
                    "error": str(exc),
                }
            )
            continue
        except Exception:
            logger.exception(
                "Unexpected risk assessment error for binary '%s'",
                prediction.binary_name,
            )
            failures.append(
                {
                    "binary_name": prediction.binary_name,
                    "error": "Unexpected risk assessment error.",
                }
            )
            continue

        try:
            _store_risk_assessment(
                db,
                firmware_id,
                prediction,
                risk_assessment,
                recommendations,
            )
        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "Failed to persist risk assessment for firmware_id=%d, binary=%s",
                firmware_id,
                prediction.binary_name,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save risk assessment results.",
            )

        assessments.append(
            RiskAssessmentResponse(
                firmware_id=firmware_id,
                binary_name=prediction.binary_name,
                algorithm_family=prediction.algorithm_family,
                algorithm=prediction.algorithm,
                confidence=prediction.confidence,
                risk_score=risk_assessment.risk_score,
                risk_level=risk_assessment.risk_level,
                risk_factors=[
                    factor.factor
                    for factor in risk_assessment.risk_factors
                    if factor.contribution > 0
                ],
                recommendations=recommendations,
            )
        )

    if not assessments:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "No valid risk assessments could be generated.",
                "failures": failures,
            },
        )

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "Failed to commit risk assessments for firmware_id=%d",
            firmware_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save risk assessment results.",
        )

    if len(assessments) == 1 and not failures:
        return assessments[0]

    return MultipleRiskAssessments(
        firmware_id=firmware_id,
        assessments=assessments,
        failed=failures,
    )


def _store_explanation_report(
    db: Session,
    analysis_id: int,
    explanation: ExplanationResult,
) -> Report:
    """Stage a report for the current transaction; do not commit here."""
    report_row = Report(
        analysis_id=analysis_id,
        rag_explanation={
            "summary": explanation.summary,
            "sections": explanation.sections,
            "references": explanation.references,
            "retrieved_documents": explanation.retrieved_documents,
            "generated_by": explanation.generated_by,
            "generation_time_ms": explanation.generation_time_ms,
        },
    )
    db.add(report_row)
    return report_row


@router.post(
    "/explain/{firmware_id}",
    response_model=None,
    summary="Run prediction, risk assessment, and an evidence-backed RAG explanation for a firmware",
)
def explain_firmware_endpoint(
    firmware_id: int, db: Session = Depends(get_db)
) -> ExplanationResponse | MultipleExplanations:
    """Run the full Phase 7 pipeline: firmware -> analysis -> ML -> risk -> RAG.

    Reuses `ml.predict` and `ml.risk`/`ml.recommend` exactly as
    `/predict` and `/risk` do, then generates an evidence-backed
    explanation (`rag.explain.explain_firmware`) citing the retrieved
    knowledge-base sources that support the conclusion. The RAG module
    never makes or changes a security decision -- it only explains
    decisions the ML and risk-assessment stages already made.

    Expects `feature_vector.json` file(s) to already exist for this
    firmware under `ANALYSIS_OUTPUT_DIR/<firmware_id>/` (Phase 4).
    """
    firmware = db.query(Firmware).filter(Firmware.id == firmware_id).first()
    if firmware is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware with id {firmware_id} was not found.",
        )

    try:
        feature_vectors = load_feature_vectors_for_firmware(firmware_id, settings.ANALYSIS_OUTPUT_DIR)
    except Exception:
        logger.exception("Unexpected error while locating feature vectors for firmware_id=%d", firmware_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while locating analysis results.",
        )

    if not feature_vectors:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No analysis results found for this firmware. Run the Firmware "
                "Analysis Engine before requesting an explanation."
            ),
        )

    try:
        predictions, prediction_failures = predict_batch(feature_vectors)
    except ModelLoadError as exc:
        logger.error("Model artifacts could not be loaded: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The prediction model is not currently available.",
        )
    except Exception:
        logger.exception("Unexpected error during prediction for firmware_id=%d", firmware_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating predictions.",
        )

    feature_vectors_by_name = dict(feature_vectors)
    firmware_age_days = (datetime.now(timezone.utc) - firmware.upload_time).days if firmware.upload_time else None
    firmware_metadata = {
        "filename": firmware.filename,
        "file_hash": firmware.file_hash,
        "upload_time": firmware.upload_time.isoformat() if firmware.upload_time else None,
        "age_days": firmware_age_days,
    }

    explanations: list[ExplanationResponse] = []
    failures = list(prediction_failures)

    for prediction in predictions:
        raw_feature_vector = feature_vectors_by_name.get(prediction.binary_name, {})
        binary_path = _find_binary_path(settings.ANALYSIS_OUTPUT_DIR, firmware_id, prediction.binary_name)
        binary_metadata = parse_elf(binary_path) if binary_path is not None else None

        try:
            risk_assessment = assess_risk(
                firmware_id=firmware_id,
                algorithm=prediction.algorithm,
                algorithm_family=prediction.algorithm_family,
                confidence=prediction.confidence,
                feature_vector=raw_feature_vector,
                binary_metadata=binary_metadata,
                firmware_metadata=firmware_metadata,
            )
            recommendations = generate_recommendations(risk_assessment.risk_factors, prediction.algorithm)

            risk_factor_dicts = [
                {"factor": rf.factor, "weight": rf.weight, "contribution": rf.contribution}
                for rf in risk_assessment.risk_factors
            ]
            explanation = explain_firmware(
                firmware_id=firmware_id,
                firmware_metadata=firmware_metadata,
                feature_vector=raw_feature_vector,
                algorithm=prediction.algorithm,
                algorithm_family=prediction.algorithm_family,
                confidence=prediction.confidence,
                risk_score=risk_assessment.risk_score,
                risk_level=risk_assessment.risk_level,
                risk_factors=risk_factor_dicts,
                recommendations=recommendations,
            )
        except (RiskConfigError, RecommendationConfigError) as exc:
            logger.error("Risk/recommendation configuration error for binary '%s': %s", prediction.binary_name, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Risk assessment configuration is invalid or unavailable.",
            )
        except (ExplanationError, RetrieverError) as exc:
            logger.error("Explanation generation error for binary '%s': %s", prediction.binary_name, exc)
            failures.append({"binary_name": prediction.binary_name, "error": str(exc)})
            continue
        except ValueError as exc:
            logger.error("Risk assessment input error for binary '%s': %s", prediction.binary_name, exc)
            failures.append({"binary_name": prediction.binary_name, "error": str(exc)})
            continue
        except Exception:
            logger.exception("Unexpected error explaining binary '%s'", prediction.binary_name)
            failures.append({"binary_name": prediction.binary_name, "error": "Unexpected explanation error."})
            continue
        try:
            analysis_row = _store_risk_assessment(
                db,
                firmware_id,
                prediction,
                risk_assessment,
                recommendations,
            )

            db.flush()  # Assign analysis_row.id without committing.

            _store_explanation_report(
                db,
                analysis_row.id,
                explanation,
            )

            db.commit()

        except SQLAlchemyError:
            db.rollback()
            logger.exception(
                "Failed to persist explanation for firmware_id=%d, binary=%s",
                firmware_id,
                prediction.binary_name,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save the explanation report.",
            )
        explanations.append(ExplanationResponse(
            firmware_id=firmware_id,
            binary_name=prediction.binary_name,
            algorithm_family=prediction.algorithm_family,
            algorithm=prediction.algorithm,
            confidence=prediction.confidence,
            risk_score=risk_assessment.risk_score,
            risk_level=risk_assessment.risk_level,
            summary=explanation.summary,
            sections=explanation.sections,
            recommendations=recommendations,
            references=explanation.references,
            generated_by=explanation.generated_by,
            generation_time_ms=explanation.generation_time_ms,
        ))

    if not explanations:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "No valid explanations could be generated.", "failures": failures},
        )

    if len(explanations) == 1 and not failures:
        return explanations[0]

    return MultipleExplanations(firmware_id=firmware_id, explanations=explanations, failed=failures)

