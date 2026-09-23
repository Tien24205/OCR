"""Diem vao cua backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
import re

from fastapi import BackgroundTasks, Depends, FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.requests import Request

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import BaseModel
from typing import Literal
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.access import NguoiGoi, doc_duoc, loc_theo_chu, nguoi_goi
from app.config import Settings, get_settings
from app.db import SessionLocal, get_db, init_db
from app.models import Scan
from app.pipeline import run_batch, run_scan
from app.services.images import ImageInputError, prepare_image
from app.services.storage import kho_anh
from app.services.drafts import DraftUpdate, apply_edit, current_draft
from app.services import erasure
from app.services.extract.unclaimed import split_text
from app.models import utcnow
from app.models import Organization, Enrichment, EnrichmentJob, norm_key
from app.services.enrich.worker import run_enrichment, job_result

settings = get_settings()


# Chan tren cho `GET /api/scans/status?ids=`: du rong cho mot lo lon nhat
# (10 anh) va cho vai lo lien tiep, du hep de mot chuoi ids dai bat thuong
# khong bien thanh mot truy van quet ca bang.
MAX_STATUS_IDS = 50

# Chan tren cho `GET /api/scans?limit=`: giao dien hien anh thu nho, moi anh
# la mot loi goi rieng - de nguoi goi tu dat limit=1000 la tu bien trang
# Kiem tra thanh mot tran 1000 lan tai anh.
MAX_LIST_SCANS = 50


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

gan_xac_thuc(app, settings.api_key_list, settings.rate_limit_per_minute,
             bi_mat_jwt=settings.jwt_signing_key,
             bat_buoc=settings.auth_required)

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

from app.user_routes import router as user_router  # noqa: E402

app.include_router(user_router)


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

    `verified` la ket qua lan XAC MINH THAT gan nhat, hoac None neu chua chay
    lan nao. Doc tu bo nho, khong goi dich vu - endpoint nay bi healthcheck goi
    10 giay mot lan.
    """
    from app.services import readiness

    return {"status": "ok", "env": config.app_env, "config": config.readiness(),
            "verified": readiness.last_result()}


@app.post("/api/readiness/verify")
def verify_readiness(config: Settings = Depends(get_settings)) -> dict:
    """Xac minh dich vu bang loi goi that. TON HAN MUC: toi da hai lan goi.

    Tach khoi /api/health vi health chay 10 giay mot lan; goi Gemini o do se
    dot han muc va tien ma khong ai yeu cau.
    """
    from app.services import readiness

    return readiness.verify(config)

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


def lay_ban_quet(db: Session, scan_id: str, nguoi: NguoiGoi,
                 ma_loi: str = "SCAN_NOT_FOUND", ten: str = "bản quét") -> Scan:
    """Nap mot ban quet VA kiem quyen doc, trong mot buoc.

    VI SAO GOP HAI VIEC LAM MOT: sau endpoint deu bat dau bang dung ba dong
    "nap - neu None thi 404 - neu khong phai cua minh thi 404". Viet roi ra
    sau cho thi cho thu bay se bi quen, va cai bi quen o day khong hong to -
    no chi lang le cho nguoi nay doc ban quet cua nguoi kia. Gop lai thi
    khong the nap ban quet ma khong kiem quyen, vi chi co mot duong nap.

    "Khong ton tai" va "khong phai cua ban" tra ve CUNG MOT cau: xem ghi chu
    dau `access.py` ve ly do khong dung 403.
    """
    scan = db.get(Scan, scan_id)
    if scan is None or not doc_duoc(scan.owner_id, nguoi):
        raise ApiError(ma_loi, f"Không tìm thấy {ten}.", 404)
    return scan


@app.post("/api/scans", status_code=201)
def create_scan(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
    session_factory=Depends(get_session_factory),
    nguoi: NguoiGoi = Depends(nguoi_goi),
) -> dict[str, str]:
    """Persist first, then process after the response using a separate session."""
    try:
        # Bounded read: never load the whole upload into application memory.
        data = file.file.read(config.max_upload_bytes + 1)
        image = prepare_image(data, config.max_upload_bytes)
        kho_anh(config).luu(image)
        scan = Scan(
            image_ref=image.digest,
            image_mime=image.mime,
            image_bytes=len(image.data),
            status="pending",
            owner_id=nguoi.user_id,
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
    nguoi: NguoiGoi = Depends(nguoi_goi),
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
            kho_anh(config).luu(image)
            scan = Scan(
                image_ref=image.digest,
                image_mime=image.mime,
                image_bytes=len(image.data),
                status="pending",
                owner_id=nguoi.user_id,
            )
            db.add(scan)
            db.commit()
            queued.append(scan.id)
            results.append({"filename": file.filename, "id": scan.id, "status": scan.status})
        except ImageInputError as exc:
            results.append({"filename": file.filename, "error": exc.message})
        except (OSError, SQLAlchemyError):
            db.rollback()
            results.append({"filename": file.filename, "error": "Lỗi hệ thống khi lưu ảnh."})
        finally:
            file.file.close()

    # Mot tac vu nen duy nhat cho ca lo: BackgroundTasks chay cac task lan luot,
    # nen xep tung anh thanh mot task se thanh chay tuan tu.
    if queued:
        background_tasks.add_task(run_batch, queued, config, session_factory)

    return {"items": results, "queued": len(queued)}


@app.get("/api/scans")
def list_scans(limit: int = 12, db: Session = Depends(get_db),
               nguoi: NguoiGoi = Depends(nguoi_goi)) -> dict:
    """Cac ban quet gan day nhat, de nguoi dung quay lai mot ban quet cu.

    VI SAO CAN: truoc endpoint nay, giao dien chi mo duoc dung ban quet vua
    gui - ma `current_scan_id` song trong phien trinh duyet. Tai lai trang la
    mat duong vao, va nhung ban quet da xu ly xong nam lai trong CSDL ma
    khong co cach nao mo ra. Da tung co 9 ban quet `ocr_done` bi ket kieu do.

    Kem `full_name`/`company_name` doc tu ban nhap de nguoi dung nhan ra the,
    va `image_ref` de hien anh thu nho.
    """
    limit = max(1, min(limit, MAX_LIST_SCANS))
    stmt = loc_theo_chu(select(Scan), Scan.owner_id, nguoi)
    rows = db.scalars(stmt.order_by(Scan.created_at.desc()).limit(limit)).all()

    items = []
    for scan in rows:
        draft = current_draft(scan.grounding_json or {}) or {}
        fields = draft.get("fields") or {}

        def dau_tien(ten_truong: str) -> str | None:
            muc = fields.get(ten_truong) or []
            return muc[0].get("value") if muc else None

        items.append({
            "id": scan.id,
            "status": scan.status,
            "image_ref": scan.image_ref,
            "created_at": scan.created_at,
            "contact_id": scan.contact_id,
            "full_name": dau_tien("full_names"),
            "company_name": dau_tien("company_names"),
        })
    return {"items": items}


# Phai khai bao TRUOC `/api/scans/{scan_id}` - xem chu thich trong ham do.
@app.get("/api/scans/status")
def scans_status(ids: str, db: Session = Depends(get_db),
                 nguoi: NguoiGoi = Depends(nguoi_goi)) -> dict:
    """Trang thai cua nhieu ban quet trong MOT loi goi.

    VI SAO CAN: giao dien theo doi mot lo dang chay bang cach hoi lai vai giay
    mot lan. Hoi tung ban quet mot thi so loi goi nhan len theo so anh - mot
    lo 10 anh moi 2 giay la 300 loi goi mot phut, trong khi gioi han la 60.
    Chinh tinh nang theo doi lai lam nguoi dung bi chan.

    Endpoint nay tra loi cho ca lo bang mot loi goi, nen chi phi khong doi
    theo so anh.
    """
    wanted = [x.strip() for x in ids.split(",") if x.strip()][:MAX_STATUS_IDS]
    if not wanted:
        return {"items": []}
    stmt = loc_theo_chu(select(Scan.id, Scan.status, Scan.error_code),
                        Scan.owner_id, nguoi)
    rows = db.execute(stmt.where(Scan.id.in_(wanted))).all()
    found = {row[0]: {"id": row[0], "status": row[1], "error_code": row[2]}
             for row in rows}
    # Giu dung thu tu ma nguoi goi hoi, va bo qua ma khong ton tai thay vi bao
    # loi ca lo: mot ma sai khong duoc lam mat trang thai cua chin ma con lai.
    return {"items": [found[i] for i in wanted if i in found]}


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db),
             nguoi: NguoiGoi = Depends(nguoi_goi)) -> dict:
    # BAY THU TU ROUTE: khai bao nay phai nam SAU `/api/scans/status`.
    # FastAPI khop route theo thu tu khai bao, nen neu `{scan_id}` dung truoc
    # thi "status" se bi nuot thanh mot ma ban quet va endpoint kia khong bao
    # gio chay - loi im lang, chi lo ra la 404 "khong tim thay ban quet".
    scan = lay_ban_quet(db, scan_id, nguoi)
    grounding = scan.grounding_json or {}
    agent_work = (scan.ocr_payload or {}).get("agent_work", {})
    selected = agent_work.get("selected_ocr")
    selected_text = agent_work["ocr_attempts"][selected]["raw_text"] if selected is not None else None
    research = db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == scan_id,
                        EnrichmentJob.draft_revision == grounding.get("draft_revision", 0)))
    draft = current_draft(grounding)
    return {
        "id": scan.id, "status": scan.status, "contact_id": scan.contact_id, "image_ref": scan.image_ref,
        "raw_text": scan.raw_text, "draft": draft,
        # Phan OCR doc duoc ma khong thuoc truong nao. Tinh luc doc chu khong
        # luu vao DB: no la phep tru tu `raw_text` va ban nhap hien tai, nen
        # luu lai chi tao them mot ban sao co the lech voi hai nguon do.
        "other_text": split_text(selected_text or scan.raw_text, draft),
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
def save_draft(scan_id: str, body: DraftUpdate, db: Session = Depends(get_db),
               nguoi: NguoiGoi = Depends(nguoi_goi)) -> dict:
    scan = lay_ban_quet(db, scan_id, nguoi)
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
    return get_scan(scan_id, db, nguoi)


@app.post("/api/scans/{scan_id}/retry", status_code=202)
def retry_scan(scan_id: str, background_tasks: BackgroundTasks,
               nguoi: NguoiGoi = Depends(nguoi_goi),
               db: Session = Depends(get_db), config: Settings = Depends(get_settings),
               session_factory=Depends(get_session_factory)) -> dict:
    # Goi de KIEM QUYEN; doi tuong tra ve khong dung den vi cau UPDATE ben
    # duoi lam viec truc tiep tren bang.
    lay_ban_quet(db, scan_id, nguoi)
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


@app.get("/api/scans/{scan_id}/image")
def get_image(scan_id: str, db: Session = Depends(get_db),
              nguoi: NguoiGoi = Depends(nguoi_goi),
              config: Settings = Depends(get_settings)):
    """Anh goc CUA MOT BAN QUET - quyen di qua ban quet, khong qua ma bam.

    LO HONG DA SUA (san-sang-thuong-mai.md, C1): duong dan cu la
    `/api/images/{image_ref}`, tra anh theo SHA-256 cua NOI DUNG anh. Ma bam
    do la mot giay thong hanh khong het han: ai cam duoc no la tai duoc anh,
    du khong lien quan gi toi ban quet - va ai co san mot ban sao cua chinh
    tam anh thi tu tinh ra ma bam, khong can he thong cap cho. Khi co nhieu
    khach hang dung chung he thong, do la ro ri du lieu ca nhan xuyen khach.

    Di qua ban quet thi phep kiem quyen sap toi (`owner_id`, Giai doan 2) chi
    co MOT cho de dat, va la cho ma moi truy van ban quet khac deu di qua.
    """
    scan = lay_ban_quet(db, scan_id, nguoi, "IMAGE_NOT_FOUND", "ảnh")
    # `image_ref` den tu CSDL chu khong tu nguoi goi nua, nhung no van bi ghep
    # vao duong dan tep - giu phep kiem de mot gia tri hong trong CSDL khong
    # tro thanh duong doc file khac tren may chu.
    if not re.fullmatch(r"[a-f0-9]{64}", scan.image_ref or ""):
        raise ApiError("IMAGE_NOT_FOUND", "Không tìm thấy ảnh.", 404)
    kho = kho_anh(config)

    # DUONG KY TAM THOI, khi kho ho tro (GCS). Trinh duyet tai thang tu nha
    # cung cap, backend khong phai bom bytes qua minh. Chi cap SAU khi
    # `lay_ban_quet()` o tren da xac nhan quyen doc - xem ghi chu dau
    # `services/storage.py` ve chuyen duong da cap thi khong con kiem duoc.
    if duong := kho.duong_ky(scan.image_ref, scan.image_mime):
        return RedirectResponse(duong, status_code=307)

    du_lieu = kho.doc(scan.image_ref)
    if du_lieu is None:
        raise ApiError("IMAGE_NOT_FOUND", "Không tìm thấy ảnh.", 404)
    return Response(du_lieu, media_type=scan.image_mime,
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@app.delete("/api/scans/{scan_id}")
def delete_scan_route(scan_id: str, nguoi: NguoiGoi = Depends(nguoi_goi),
                      db: Session = Depends(get_db),
                      config: Settings = Depends(get_settings)):
    """Xoa han mot ban quet va anh goc cua no.

    Anh luu theo SHA-256 nen hai ban quet co the dung chung mot tep - anh chi
    bi xoa khi khong con ban quet nao tro toi. Xem `services/erasure.py`.

    Ho so da luu tu ban quet nay KHONG bi xoa theo: no la thu nguoi dung co y
    giu lai. Muon xoa ca hai thi goi `DELETE /api/contacts/{id}`.
    """
    scan = lay_ban_quet(db, scan_id, nguoi)
    return erasure.delete_scan(db, scan, kho_anh(config))


class ResearchRequest(BaseModel):
    revision: int


@app.post("/api/scans/{scan_id}/enrich", status_code=202)
def research_scan(scan_id: str, body: ResearchRequest, background_tasks: BackgroundTasks,
                  nguoi: NguoiGoi = Depends(nguoi_goi),
                  db: Session = Depends(get_db), config: Settings = Depends(get_settings),
                  session_factory=Depends(get_session_factory)):
    if not config.enrich_enabled:
        raise ApiError("ENRICH_DISABLED", "Tra cứu đang tắt trong cấu hình.", 409)
    scan = lay_ban_quet(db, scan_id, nguoi)
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
