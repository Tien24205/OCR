"""Diem vao cua backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
import re

from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import BaseModel
from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal, get_db, init_db
from app.models import Scan
from app.pipeline import run_batch, run_scan
from app.services.images import ImageInputError, prepare_image, store_image
from app.services.drafts import DraftUpdate, apply_edit, current_draft
from app.models import utcnow
from app.models import Organization, Enrichment, EnrichmentJob, norm_key
from app.services.enrich.worker import run_enrichment, job_result

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Business Card to Partner Profile",
    version="0.1.0",
    lifespan=lifespan,
)

# Gan TRUOC CORS de lop xac thuc nam ngoai cung: mot loi goi khong co khoa bi
# chan ngay, khong di sau vao ung dung.
from app.auth import gan_xac_thuc  # noqa: E402

gan_xac_thuc(app, settings.api_key_list, settings.rate_limit_per_minute)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.errors import ApiError
from app.contact_routes import router as contact_router

app.include_router(contact_router)

from app.webhook import router as webhook_router  # noqa: E402

app.include_router(webhook_router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
            }
        },
    )


@app.get("/api/health")
def health(config: Settings = Depends(get_settings)) -> dict:
    """Kiem tra ung dung song va cau hinh da san sang chua.

    `readiness()` chi tra ve True/False - khong bao gio lo gia tri khoa.
    """
    return {"status": "ok", "env": config.app_env, "config": config.readiness()}

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)) -> dict:
    """So lieu tong quan cho trang Bang dieu khien.

    Giu lai ba khoa `total_*` cua ban dau de khong pha vo thu da goi endpoint
    nay; phan con lai nam trong cac khoa moi.
    """
    from app.services.stats import collect

    data = collect(db)
    totals = data["totals"]
    return {
        "total_scans": totals["scans"],
        "total_contacts": totals["contacts"],
        "total_organizations": totals["organizations"],
        **data,
    }

def get_session_factory():
    return SessionLocal


@app.post("/api/scans", status_code=201)
def create_scan(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
) -> dict[str, str]:
    """Persist first, then process after the response using a separate session."""
    try:
        # Bounded read: never load the whole upload into application memory.
        data = file.file.read(config.max_upload_bytes + 1)
        image = prepare_image(data, config.max_upload_bytes)
        store_image(image, config.image_path)
        scan = Scan(
            image_ref=image.digest,
            image_mime=image.mime,
            image_bytes=len(image.data),
            status="pending",
        )
        db.add(scan)
        db.commit()
        background_tasks.add_task(run_scan, scan.id, config, session_factory)
        return {"id": scan.id, "status": scan.status}
    except ImageInputError as exc:
        raise ApiError(exc.code, exc.message, exc.status) from exc
    except (OSError, SQLAlchemyError) as exc:
        db.rollback()
        # A shared hash file may be used by another scan; never delete it here.
        raise ApiError(
            "SCAN_SAVE_FAILED", "Chưa lưu được ảnh. Vui lòng thử lại.", 500, True
        ) from exc
    finally:
        file.file.close()


@app.post("/api/scans/batch", status_code=201)
def create_batch_scans(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
) -> dict:
    """Xử lý hàng loạt nhiều ảnh trong một lần gửi.

    Ảnh hỏng không làm hỏng cả lô: mỗi ảnh có mục kết quả riêng, ảnh lỗi trả về
    khoá `error` còn ảnh hợp lệ vẫn được xếp hàng xử lý.
    """
    if len(files) > config.batch_max_images:
        raise ApiError(
            "BATCH_TOO_LARGE",
            f"Chỉ hỗ trợ tối đa {config.batch_max_images} ảnh mỗi lần.", 400)

    results, queued = [], []
    for file in files:
        try:
            data = file.file.read(config.max_upload_bytes + 1)
            image = prepare_image(data, config.max_upload_bytes)
            store_image(image, config.image_path)
            scan = Scan(
                image_ref=image.digest,
                image_mime=image.mime,
                image_bytes=len(image.data),
                status="pending",
            )
            db.add(scan)
            db.commit()
            queued.append(scan.id)
            results.append({"filename": file.filename, "id": scan.id, "status": scan.status})
        except ImageInputError as exc:
            results.append({"filename": file.filename, "error": exc.message})
        except (OSError, SQLAlchemyError) as exc:
            db.rollback()
            results.append({"filename": file.filename, "error": "Lỗi hệ thống khi lưu ảnh."})
        finally:
            file.file.close()

    # Mot tac vu nen duy nhat cho ca lo: BackgroundTasks chay cac task lan luot,
    # nen xep tung anh thanh mot task se thanh chay tuan tu.
    if queued:
        background_tasks.add_task(run_batch, queued, config, session_factory)

    return {"items": results, "queued": len(queued)}

@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)) -> dict:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
    grounding = scan.grounding_json or {}
    agent_work = (scan.ocr_payload or {}).get("agent_work", {})
    selected = agent_work.get("selected_ocr")
    selected_text = agent_work["ocr_attempts"][selected]["raw_text"] if selected is not None else None
    research = db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == scan_id,
                        EnrichmentJob.draft_revision == grounding.get("draft_revision", 0)))
    return {
        "id": scan.id, "status": scan.status, "contact_id": scan.contact_id, "image_ref": scan.image_ref,
        "raw_text": scan.raw_text, "draft": current_draft(grounding),
        "ocr_text_for_draft": selected_text,
        "draft_revision": grounding.get("draft_revision", 0),
        "draft_saved_at": grounding.get("draft_saved_at"),
        "enrichment": job_result(db, research),
        "grounding": {key: value for key, value in grounding.items()
                      if key not in {"draft", "reviewed_draft", "draft_revision", "draft_saved_at"}},
        "detected_languages": scan.detected_langs or [],
        "ocr_provider": scan.ocr_provider, "ocr_version": scan.ocr_version,
        "extractor": scan.extractor,
        "extraction_config": (scan.ocr_payload or {}).get("extraction_config"),
        "is_mock": bool(scan.ocr_provider and scan.ocr_provider.startswith("mock")),
        "error_code": scan.error_code, "error_message": scan.error_message,
        "retry_count": scan.retry_count, "can_retry": scan.status == "failed" and scan.retry_count < 3 and scan.error_code != "IMAGE_RECAPTURE_REQUIRED",
        "ms_ocr": scan.ms_ocr, "ms_extract": scan.ms_extract,
        "created_at": scan.created_at, "completed_at": scan.completed_at,
    }


@app.patch("/api/scans/{scan_id}/draft")
def save_draft(scan_id: str, body: DraftUpdate, db: Session = Depends(get_db)) -> dict:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
    grounding = scan.grounding_json or {}
    draft = current_draft(grounding)
    if scan.status != "ocr_done" or draft is None:
        raise ApiError("DRAFT_NOT_EDITABLE", "Chỉ sửa bản nháp đã xử lý OCR xong.", 409)
    if body.revision != grounding.get("draft_revision", 0):
        raise ApiError("DRAFT_CONFLICT", "Bản nháp đã được lưu ở nơi khác. Tải lại trước khi sửa tiếp.", 409)
    try:
        edited = apply_edit(draft, body.fields)
    except ValueError as exc:
        raise ApiError("INVALID_DRAFT", str(exc), 422) from exc
    replacement = {**grounding, "reviewed_draft": edited,
                   "draft_revision": body.revision + 1, "draft_saved_at": utcnow()}
    try:
        changed = db.execute(update(Scan).where(
            Scan.id == scan_id, Scan.status == "ocr_done", Scan.grounding_json == grounding
        ).values(grounding_json=replacement).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            db.rollback()
            raise ApiError("DRAFT_CONFLICT", "Bản nháp vừa thay đổi. Tải lại trước khi lưu.", 409)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError("DRAFT_SAVE_FAILED", "Chưa lưu được bản nháp. Giữ form và thử lại.", 500, True) from exc
    db.expire_all()
    return get_scan(scan_id, db)


@app.post("/api/scans/{scan_id}/retry", status_code=202)
def retry_scan(scan_id: str, background_tasks: BackgroundTasks,
               db: Session = Depends(get_db), config: Settings = Depends(get_settings),
               session_factory=Depends(get_session_factory)) -> dict:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
    changed = db.execute(update(Scan).where(
        Scan.id == scan_id, Scan.status == "failed", Scan.retry_count < 3,
        (Scan.error_code.is_(None) | (Scan.error_code != "IMAGE_RECAPTURE_REQUIRED"))
    ).values(status="pending", retry_count=Scan.retry_count + 1,
             error_code=None, error_message=None, completed_at=None))
    db.commit()
    if changed.rowcount != 1:
        raise ApiError("RETRY_NOT_ALLOWED", "Chỉ thử lại bản quét lỗi, tối đa 3 lần.", 409)
    background_tasks.add_task(run_scan, scan_id, config, session_factory)
    return {"id": scan_id, "status": "pending"}


@app.get("/api/images/{image_ref}")
def get_image(image_ref: str, db: Session = Depends(get_db), config: Settings = Depends(get_settings)):
    if not re.fullmatch(r"[a-f0-9]{64}", image_ref):
        raise ApiError("IMAGE_NOT_FOUND", "Không tìm thấy ảnh.", 404)
    scan = db.scalar(select(Scan).where(Scan.image_ref == image_ref).limit(1))
    path = config.image_path / image_ref
    if scan is None or not path.is_file():
        raise ApiError("IMAGE_NOT_FOUND", "Không tìm thấy ảnh.", 404)
    return FileResponse(path, media_type=scan.image_mime,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


class ResearchRequest(BaseModel):
    revision: int


@app.post("/api/scans/{scan_id}/enrich", status_code=202)
def research_scan(scan_id: str, body: ResearchRequest, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db), config: Settings = Depends(get_settings),
                  session_factory=Depends(get_session_factory)):
    if not config.enrich_enabled:
        raise ApiError("ENRICH_DISABLED", "Tra cứu đang tắt trong cấu hình.", 409)
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ApiError("SCAN_NOT_FOUND", "Không tìm thấy bản quét.", 404)
    grounding = scan.grounding_json or {}
    if scan.status not in {"ocr_done", "committed"} or body.revision != grounding.get("draft_revision", 0):
        raise ApiError("DRAFT_CONFLICT", "Lưu hoặc tải lại bản nháp đã xử lý trước khi tra cứu.", 409)
    draft = current_draft(grounding)
    if draft is None:
        raise ApiError("DRAFT_NOT_READY", "Chưa có bản nháp để tra cứu.", 409)
    def existing_job():
        return db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == scan_id,
                          EnrichmentJob.draft_revision == body.revision))
    job = existing_job()
    if job:
        return job_result(db, job)
    names = draft["fields"].get("company_names", [])
    organization = Organization(name_original=names[0]["value"] if names else "",
                                name_norm=norm_key(names[0]["value"] if names else ""))
    # Candidate domains remain research input; do not populate card data with them.
    try:
        db.add(organization)
        db.flush()
        job = EnrichmentJob(scan_id=scan_id, organization_id=organization.id,
                            draft_revision=body.revision, snapshot=draft)
        db.add(job)
        db.commit()
    except IntegrityError:
        db.rollback()
        job = existing_job()
        if job is None:
            raise ApiError("ENRICH_SAVE_FAILED", "Chưa tạo được lượt tra cứu.", 500, True)
        return job_result(db, job)
    except SQLAlchemyError as exc:
        db.rollback()
        raise ApiError("ENRICH_SAVE_FAILED", "Chưa tạo được lượt tra cứu.", 500, True) from exc
    background_tasks.add_task(run_enrichment, job.id, config, session_factory)
    return job_result(db, job)


@app.get("/api/organizations/{organization_id}")
def get_organization(organization_id: str, db: Session = Depends(get_db)):
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise ApiError("ORGANIZATION_NOT_FOUND", "Không tìm thấy doanh nghiệp.", 404)
    job = db.scalar(select(EnrichmentJob).where(EnrichmentJob.organization_id == organization_id))
    return {"id": organization.id, "name_original": organization.name_original, "research": job_result(db, job)}


@app.post("/api/organizations/{organization_id}/enrich", status_code=202)
def retry_research(organization_id: str, background_tasks: BackgroundTasks,
                   db: Session = Depends(get_db), config: Settings = Depends(get_settings),
                   session_factory=Depends(get_session_factory)):
    if not config.enrich_enabled:
        raise ApiError("ENRICH_DISABLED", "Tra cứu đang tắt trong cấu hình.", 409)
    job = db.scalar(select(EnrichmentJob).where(EnrichmentJob.organization_id == organization_id))
    if job is None:
        raise ApiError("RESEARCH_NOT_FOUND", "Chưa có đầu vào tra cứu của doanh nghiệp này.", 404)
    if job.status in {"pending", "processing"}:
        return job_result(db, job)
    changed = db.execute(update(EnrichmentJob).where(EnrichmentJob.id == job.id,
                        EnrichmentJob.status == "done", EnrichmentJob.attempts < 3)
                        .values(status="pending", attempts=EnrichmentJob.attempts + 1, reason=None,
                                result_ids=[], pages=[], metadata_json={}, completed_at=None)
                        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise ApiError("RESEARCH_RETRY_LIMIT", "Tối đa 3 lượt tra cứu cho mỗi phiên bản bản nháp.", 409)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_enrichment, job.id, config, session_factory)
    return job_result(db, job)


class ClaimDecision(BaseModel):
    decision: Literal["accepted", "rejected"]


@app.patch("/api/enrichments/{enrichment_id}")
def review_claim(enrichment_id: str, body: ClaimDecision, db: Session = Depends(get_db)):
    row = db.get(Enrichment, enrichment_id)
    if row is None:
        raise ApiError("ENRICHMENT_NOT_FOUND", "Không tìm thấy thông tin bổ sung.", 404)
    job = db.scalar(select(EnrichmentJob).where(EnrichmentJob.organization_id == row.organization_id))
    if job is None or job.status != "done" or enrichment_id not in job.result_ids or row.value is None:
        raise ApiError("CLAIM_NOT_REVIEWABLE", "Thông tin này chưa thể duyệt hoặc đã thuộc lượt tra cứu cũ.", 409)
    decisions = dict(job.decisions)
    decisions[enrichment_id] = body.decision
    if body.decision == "accepted" and row.status == "conflicting":
        alternatives = db.scalars(select(Enrichment).where(Enrichment.id.in_(job.result_ids),
                                  Enrichment.attribute == row.attribute, Enrichment.id != row.id)).all()
        for alternative in alternatives:
            if decisions.get(alternative.id) == "accepted":
                decisions[alternative.id] = "rejected"
                alternative.reviewed = True
    changed = db.execute(update(EnrichmentJob).where(EnrichmentJob.id == job.id,
                        EnrichmentJob.status == "done", EnrichmentJob.decisions == job.decisions,
                        EnrichmentJob.result_ids == job.result_ids).values(decisions=decisions)
                        .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise ApiError("REVIEW_CONFLICT", "Kết quả vừa thay đổi. Tải lại trước khi duyệt.", 409)
    row.reviewed = True
    db.commit()
    db.refresh(job)
    return job_result(db, job)


# PHAI o CUOI FILE: apply() duyet `app.routes`, nen moi endpoint khai bao
# sau lenh goi nay se khong duoc gan mo ta. Dat ngay sau include_router()
# thi phan lon endpoint cua chinh file nay con chua ton tai.
from app.api_docs import apply as apply_api_docs  # noqa: E402

apply_api_docs(app)
