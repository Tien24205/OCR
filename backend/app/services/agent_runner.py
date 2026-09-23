"""Result-dependent orchestration. At most two automatic retries per scan.

First successful raw OCR/extraction remain immutable. Selected attempts have
their own checkpoints so review can distinguish them from initial evidence.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import logging
import time

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.models import Scan, Organization, EnrichmentJob, norm_key, utcnow
from app.services.agent_orchestrator import Action
from app.services.image_quality import ImageQualityAgent, contrast_variant
from app.services.ocr.base import OcrError
from app.services.extract.base import ExtractionError, CardExtraction
from app.services.extract.grounding import ground_extraction
from app.services.confidence import ConfidenceAgent
from app.services.normalize import normalize_draft
from app.services.enrich.discover import seed_url
from app.services.storage import doc_anh

logger = logging.getLogger(__name__)


def missing(grounding):
    return [field for field in ("full_names", "company_names") if not grounding["fields"][field]]


def rank(grounding):
    counts = grounding["counts"]
    return (2 - len(missing(grounding)), -counts["unverified"], counts["exact"], counts["fuzzy"])


def run(controller, scan_id, config, session_factory):
    # Use the same injectable provider factory as the legacy worker.
    from app import pipeline
    provider = extractor = None
    auto_draft = None
    with session_factory() as db:
        claimed = db.execute(update(Scan).where(Scan.id == scan_id, Scan.status == "pending")
                             .values(status="processing", error_code=None, error_message=None))
        db.commit()
        if claimed.rowcount != 1:
            return
        scan = db.get(Scan, scan_id)
        state = deepcopy((scan.ocr_payload or {}).get("agent_work", {
            "version": 1, "retries": 0, "ocr_attempts": [], "extraction_attempts": []}))
        old_ground = deepcopy(scan.grounding_json or {})
        previous_log = old_ground.get("agent_decisions", [])

        def log(agent, action, reason, **metadata):
            # Policy scores are not probabilities; keep sensitive provider errors out.
            controller.record_decision(agent, action, reason, 0.0, **metadata)

        def checkpoint():
            scan.ocr_payload = {**(scan.ocr_payload or {}), "agent_work": deepcopy(state)}
            scan.grounding_json = {**(scan.grounding_json or {}), "agent_mode": True,
                "agent_decisions": previous_log + controller.get_decisions_log()}
            db.commit()

        def reserve_retry(agent, reason, **metadata):
            if state["retries"] >= 2:
                return False
            state["retries"] += 1
            log(agent, Action.RETRY, reason, retry_number=state["retries"], **metadata)
            checkpoint()  # Persist reservation before the external call.
            return True

        try:
            image = doc_anh(config, scan.image_ref)
            quality = ImageQualityAgent().assess(image)
            state["quality"] = quality
            if quality["action"] == "recapture" and not scan.raw_text:
                log("image_quality_agent", Action.ESCALATE, "Chất lượng ảnh quá thấp; cần chụp lại.", assessment=quality)
                checkpoint()
                raise OcrError("IMAGE_RECAPTURE_REQUIRED", "Ảnh quá mờ, thiếu chi tiết hoặc quá nhỏ. Hãy chụp/tải ảnh mới.")
            log("image_quality_agent", Action.PROCEED,
                "Tiếp tục; kiểm tra cảnh báo chất lượng ảnh." if quality["issues"] else "Ảnh đạt kiểm tra sơ bộ.", assessment=quality)

            # A completed OCR checkpoint is reused after an extraction failure.
            if "selected_ocr" not in state and scan.raw_text:
                state["ocr_attempts"].append({"raw_text": scan.raw_text, "blocks": (scan.ocr_payload or {}).get("blocks", []),
                    "provider": scan.ocr_provider, "provider_version": scan.ocr_version,
                    "detected_languages": scan.detected_langs or [], "variant": "original_checkpoint"})
                state["selected_ocr"] = len(state["ocr_attempts"]) - 1
            if "selected_ocr" not in state:
                provider = pipeline.build_ocr(config)
                candidate_image, candidate_mime, variant = image, scan.image_mime, "original"
                started = time.perf_counter()
                while True:
                    attempt = {"variant": variant, "image_sha256": hashlib.sha256(candidate_image).hexdigest(),
                               "started_at": utcnow()}
                    try:
                        response = provider.recognize(candidate_image, candidate_mime)
                    except OcrError as exc:
                        attempt["error_type"] = type(exc).__name__
                        state["ocr_attempts"].append(attempt)
                        checkpoint()
                        if exc.retryable and reserve_retry("ocr_agent", "Lỗi OCR tạm thời; thử lại có giới hạn."):
                            pipeline._sleep(0.5)
                            continue
                        if "selected_ocr" in state:
                            log("ocr_agent", Action.ESCALATE, "Lần thử bổ sung lỗi; giữ kết quả OCR trước đó.")
                            break
                        raise
                    attempt.update(asdict(response))
                    state["ocr_attempts"].append(attempt)
                    index = len(state["ocr_attempts"]) - 1
                    confidences = [b.confidence for b in response.blocks if b.confidence is not None]
                    score = sum(confidences)/len(confidences) if confidences else None
                    attempt["mean_confidence"] = score
                    if response.raw_text.strip():
                        current = state["ocr_attempts"][state["selected_ocr"]] if "selected_ocr" in state else None
                        if current is None or (score is not None and score > (current.get("mean_confidence") or 0)):
                            state["selected_ocr"] = index
                        if scan.raw_text is None:
                            scan.raw_text, scan.ocr_provider, scan.ocr_version = response.raw_text, response.provider, response.provider_version
                            scan.detected_langs = response.detected_languages
                            scan.ocr_payload = {**(scan.ocr_payload or {}), "response": response.payload,
                                                "blocks": [asdict(b) for b in response.blocks], "recorded_at": utcnow()}
                    checkpoint()
                    low = not response.raw_text.strip() or (score is not None and score < 0.6)
                    if low and variant == "original" and reserve_retry("ocr_agent", "OCR thiếu chữ/điểm thấp; thử tăng tương phản.", strategy="contrast"):
                        candidate_image, candidate_mime, variant = contrast_variant(image), "image/png", "contrast"
                        continue
                    break
                scan.ms_ocr = int((time.perf_counter() - started) * 1000)
                if "selected_ocr" not in state:
                    raise OcrError("OCR_EMPTY", "Không đọc được chữ sau các lần thử. Hãy chọn ảnh rõ hơn.")
                log("ocr_agent", Action.PROCEED, "Đã chọn kết quả OCR có văn bản.", selected_attempt=state["selected_ocr"])
                checkpoint()
            selected_ocr = state["ocr_attempts"][state["selected_ocr"]]
            text = selected_ocr["raw_text"]

            if scan.extraction_json is not None and not state["extraction_attempts"]:
                state["extraction_attempts"].append({"strategy": "original_checkpoint", "result": scan.extraction_json})
            successful = [x for x in state["extraction_attempts"] if "result" in x]
            if not successful:
                extractor = pipeline.build_extractor(config)
                scan.extractor = extractor.name
                scan.ocr_payload = {**(scan.ocr_payload or {}), "extraction_config": {
                    "provider": extractor.name, "model": config.gemini_model if config.extractor == "gemini" else None}}
                started = time.perf_counter()
                strategy = "initial"
                while True:
                    try:
                        response = extractor.extract(image, scan.image_mime, text)
                        scan.extraction_json = response.model_dump()  # First success only.
                        state["extraction_attempts"].append({"strategy": strategy, "result": scan.extraction_json})
                        checkpoint()
                        break
                    except ExtractionError as exc:
                        state["extraction_attempts"].append({"strategy": strategy, "error_type": type(exc).__name__})
                        checkpoint()
                        if not exc.retryable or not reserve_retry("extraction_agent", "Lỗi trích xuất tạm thời; thử lại có giới hạn."):
                            raise
                scan.ms_extract = int((time.perf_counter() - started) * 1000)
            successful = [x for x in state["extraction_attempts"] if "result" in x]
            best = max(successful, key=lambda x: rank(ground_extraction(CardExtraction.model_validate(x["result"]), text)))
            grounded = ground_extraction(CardExtraction.model_validate(best["result"]), text)
            counts = grounded["counts"]
            rejected_ratio = counts["unverified"] / max(sum(counts.values()), 1)
            needs_retry = missing(grounded) or rejected_ratio >= 0.5
            if needs_retry and not any(x["strategy"] == "alternative_prompt" for x in state["extraction_attempts"]):
                if extractor is None:
                    extractor = pipeline.build_extractor(config)
                retry_method = getattr(extractor, "extract_retry", None)
                if callable(retry_method) and reserve_retry("extraction_agent", "Thiếu tên/công ty hoặc nhiều trường không khớp; đọc lại bằng prompt khác.",
                                                          missing=missing(grounded), rejected_ratio=rejected_ratio):
                    try:
                        response = retry_method(image, scan.image_mime, text)
                        candidate = {"strategy": "alternative_prompt", "result": response.model_dump()}
                        state["extraction_attempts"].append(candidate)
                        alternate = ground_extraction(response, text)
                        if rank(alternate) > rank(grounded):
                            best, grounded = candidate, alternate
                    except Exception as exc:
                        state["extraction_attempts"].append({"strategy": "alternative_prompt", "error_type": type(exc).__name__})
                        log("extraction_agent", Action.ESCALATE, "Lần đọc bổ sung thất bại; giữ kết quả đã đối chiếu.")
                    checkpoint()
                else:
                    log("extraction_agent", Action.ESCALATE, "Cần kiểm tra tay; extractor không có prompt khác hoặc đã hết ngân sách retry.")
            state["selected_extraction"] = state["extraction_attempts"].index(best)
            warnings = []
            if missing(grounded):
                warnings.append("Chưa đọc được tên hoặc công ty. Hãy đối chiếu ảnh và bổ sung nếu có.")
            if grounded["counts"]["unverified"]:
                warnings.append("Một số trường không khớp văn bản OCR đã bị loại. Kiểm tra trên ảnh trước khi lưu.")
            log("grounding_agent", Action.ESCALATE if warnings else Action.PROCEED,
                "Cần người dùng đối chiếu các trường thiếu/bị loại." if warnings else "Các trường đã được đối chiếu với OCR.", counts=grounded["counts"])
            draft = normalize_draft(grounded)
            # Nhanh agent truoc day khong cham diem tin cay, nen hai nhanh cho
            # ket qua khac nhau tren cung mot anh. Cham o day de dong nhat.
            confidence = ConfidenceAgent().evaluate_scan(
                draft, scan.detected_langs or []
            )
            log("normalize_agent", Action.PROCEED, "Chuẩn hóa và giữ nguồn dữ liệu; không suy đoán trường trống.")
            url, _ = seed_url(draft)
            if config.agent_auto_enrich and config.enrich_enabled and url:
                auto_draft = draft
                log("enrichment_agent", Action.PROCEED, "Có nguồn trên thẻ; lên lịch tra cứu độc lập sau khi lưu OCR.")
            else:
                log("enrichment_agent", Action.SKIP, "Tra cứu tự động tắt hoặc chưa có domain; người dùng có thể tra cứu sau khi duyệt.")
            scan.grounding_json = {**grounded, "draft": draft, "agent_selected_draft": draft,
                                   "confidence": confidence,
                                   "agent_warnings": warnings, "agent_mode": True}
            scan.status, scan.completed_at = "ocr_done", utcnow()
            checkpoint()
        except Exception as exc:
            db.rollback()
            scan = db.get(Scan, scan_id)
            log("pipeline", Action.ESCALATE, "Dừng xử lý; xem thông báo lỗi hoặc chụp lại.", error_type=type(exc).__name__)
            scan.status, scan.completed_at = "failed", utcnow()
            # Never persist arbitrary provider exception text, even known errors.
            if isinstance(exc, OcrError) and exc.code == "IMAGE_RECAPTURE_REQUIRED":
                scan.error_code, scan.error_message = exc.code, "Ảnh quá kém để nhận diện. Hãy chụp/tải ảnh mới."
            else:
                scan.error_code, scan.error_message = "AGENT_PROCESSING_FAILED", "Chưa xử lý được bản quét. Kiểm tra cấu hình hoặc thử lại."
            checkpoint()
        finally:
            for service in (provider, extractor):
                if callable(getattr(service, "close", None)):
                    try:
                        service.close()
                    except Exception:
                        pass
    if auto_draft:
        auto_enrich(scan_id, auto_draft, config, session_factory)


def auto_enrich(scan_id, draft, config, factory):
    """Separate transaction and failure boundary: enrichment never fails OCR."""
    from app.services.enrich.worker import run_enrichment
    job_id = None
    try:
        with factory() as db:
            existing = db.scalar(select(EnrichmentJob).where(EnrichmentJob.scan_id == scan_id, EnrichmentJob.draft_revision == 0))
            if existing:
                return
            names = draft["fields"]["company_names"]
            org = Organization(name_original=names[0]["value"] if names else "", name_norm=norm_key(names[0]["value"] if names else ""))
            db.add(org)
            db.flush()
            job = EnrichmentJob(scan_id=scan_id, organization_id=org.id, draft_revision=0, snapshot=draft)
            db.add(job)
            db.commit()
            job_id = job.id
        run_enrichment(job_id, config, factory)
    except IntegrityError:
        pass  # A manual request already reserved this scan/revision.
    except Exception:
        logger.warning("Automatic research failed for scan %s", scan_id)
        if job_id:
            with factory() as db:
                db.execute(update(EnrichmentJob).where(EnrichmentJob.id == job_id,
                           EnrichmentJob.status.in_(["pending", "processing"]))
                           .values(status="done", reason="ENRICH_FAILED", completed_at=utcnow()))
                db.commit()
