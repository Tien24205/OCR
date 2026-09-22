"""In-process Day 4 worker. Each job owns its session and commits checkpoints."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import logging
import time
from time import sleep as _sleep

from sqlalchemy import update

from app.config import Settings
from app.models import Scan, utcnow
from app.services.providers import build_ocr, build_extractor
from app.services.ocr.base import OcrError
from app.services.extract.base import CardExtraction, ExtractionError
from app.services.extract.grounding import ground_extraction
from app.services.normalize import normalize_draft
from app.services.agent_orchestrator import AgenticOrchestrator, Action
from app.services.image_quality import ImageQualityAgent
from app.services.confidence import ConfidenceAgent

logger = logging.getLogger(__name__)


def _recognize(provider, image: bytes, mime: str):
    for attempt in range(3):  # Initial request + at most two transient retries.
        try:
            return provider.recognize(image, mime)
        except OcrError as exc:
            if not exc.retryable or attempt == 2:
                raise
            _sleep(0.5 * (2 ** attempt))


def run_scan(scan_id: str, config: Settings, session_factory) -> None:
    try:
        if config.agent_enabled:
            AgenticOrchestrator().run(scan_id, config, session_factory)
            return
        run_legacy_scan(scan_id, config, session_factory)
    finally:
        # Han luu tru chi co y nghia khi co du lieu chay qua, nen cho don o
        # day: cham nhat mot lan moi gio, va ngoai duong yeu cau. Chay ca khi
        # ban quet nay loi - anh van da duoc luu.
        from app.services.erasure import maybe_purge
        maybe_purge(config, session_factory)


def run_legacy_scan(scan_id: str, config: Settings, session_factory) -> None:
    with session_factory() as db:
        claimed = db.execute(update(Scan).where(
            Scan.id == scan_id, Scan.status == "pending"
        ).values(status="processing", error_code=None, error_message=None, completed_at=None))
        db.commit()
        if claimed.rowcount != 1:
            return
        scan = db.get(Scan, scan_id)
        provider = extractor = None
        stage = "image_quality"
        started = time.perf_counter()
        orchestrator = AgenticOrchestrator()
        try:
            image = (config.image_path / scan.image_ref).read_bytes()

            # Agent 1: Image Quality
            qa_agent = ImageQualityAgent()
            quality = qa_agent.evaluate(image)
            if not quality["acceptable"]:
                orchestrator.record_decision("image_quality_agent", Action.ESCALATE,
                                             f"Image quality issues: {', '.join(quality['issues'])}", 0.9, **quality["metrics"])
            else:
                orchestrator.record_decision("image_quality_agent", Action.PROCEED,
                                             "Image quality is acceptable", 0.95, **quality["metrics"])

            stage = "ocr"
            # Successful evidence is immutable across retries.
            if not scan.raw_text:
                provider = build_ocr(config)

                def _do_ocr():
                    return _recognize(provider, image, scan.image_mime)

                # _recognize already owns the bounded transient retry policy.
                result = orchestrator.execute_with_retry("ocr_agent", _do_ocr, max_retries=0)

                scan.raw_text = result.raw_text
                scan.ocr_provider = result.provider
                scan.ocr_version = result.provider_version
                scan.detected_langs = result.detected_languages
                scan.ms_ocr = int((time.perf_counter() - started) * 1000)
                scan.ocr_payload = {"response": result.payload,
                                    "blocks": [asdict(block) for block in result.blocks],
                                    "recorded_at": utcnow()}
                db.commit()
            if not scan.raw_text.strip():
                raise OcrError("OCR_EMPTY", "Không đọc được chữ. Hãy chọn ảnh rõ hơn.")

            stage = "extract"
            started = time.perf_counter()
            if scan.extraction_json is None:
                extractor = build_extractor(config)
                scan.extractor = extractor.name
                scan.ocr_payload = {**(scan.ocr_payload or {}), "extraction_config": {
                    "provider": extractor.name,
                    "model": config.gemini_model if config.extractor == "gemini" else None,
                    "temperature": config.gemini_temperature if config.extractor == "gemini" else None,
                }}
                db.commit()

                def _do_extract():
                    return extractor.extract(image, scan.image_mime, scan.raw_text)

                extraction = orchestrator.execute_with_retry("extraction_agent", _do_extract, max_retries=1,
                    retry_condition=lambda exc: isinstance(exc, ExtractionError) and exc.retryable)

                scan.extraction_json = extraction.model_dump()
                scan.ms_extract = int((time.perf_counter() - started) * 1000)
                db.commit()
            else:
                extraction = CardExtraction.model_validate(scan.extraction_json)

            stage = "ground"
            # Agent 3: Grounding
            def _do_grounding():
                return ground_extraction(extraction, scan.raw_text)

            grounding = orchestrator.execute_with_retry("grounding_agent", _do_grounding, max_retries=0)
            grounding["draft"] = normalize_draft(grounding)

            # Agent 4: Confidence Scoring
            conf_agent = ConfidenceAgent()
            scan_langs = scan.detected_langs or []
            conf_result = conf_agent.evaluate_scan(grounding["draft"], scan_langs)
            grounding["confidence"] = conf_result

            if conf_result["overall_score"] < 0.5:
                orchestrator.record_decision("confidence_agent", Action.ESCALATE,
                                             f"Low overall confidence ({conf_result['overall_score']})",
                                             conf_result["overall_score"])
            else:
                orchestrator.record_decision("confidence_agent", Action.PROCEED,
                                             "Confidence is acceptable",
                                             conf_result["overall_score"])

            # Record agent decisions into grounding
            grounding["agent_decisions"] = orchestrator.get_decisions_log()

            scan.grounding_json = grounding
            scan.status = "ocr_done"
            scan.completed_at = utcnow()
            db.commit()
            notify_completed(scan_id, grounding, config, session_factory)
        except Exception as exc:
            db.rollback()
            scan = db.get(Scan, scan_id)
            if scan is not None:
                if stage == "ocr" and not scan.raw_text:
                    scan.ms_ocr = int((time.perf_counter() - started) * 1000)
                if stage == "extract" and scan.extraction_json is None:
                    scan.ms_extract = int((time.perf_counter() - started) * 1000)
                known = isinstance(exc, (OcrError, ExtractionError))
                scan.error_code = exc.code if known else "SCAN_PROCESSING_FAILED"
                scan.error_message = exc.message if known else "Chưa xử lý được bản quét. Kiểm tra ảnh và cấu hình backend."
                scan.status = "failed"
                scan.completed_at = utcnow()
                # Include decisions even on failure
                if scan.grounding_json is None:
                    scan.grounding_json = {}
                current_grounding = dict(scan.grounding_json)
                current_grounding["agent_decisions"] = orchestrator.get_decisions_log()
                scan.grounding_json = current_grounding
                db.commit()
            # Do not log provider exception text: it may include request content.
            logger.warning("Scan %s failed at %s (%s)", scan_id, stage, type(exc).__name__)
        finally:
            for service in (provider, extractor):
                close = getattr(service, "close", None)
                if close:
                    try:
                        close()
                    except Exception:
                        logger.warning("Provider close failed for scan %s", scan_id)


def run_batch(scan_ids: list[str], config: Settings, session_factory) -> None:
    """Chay nhieu ban quet voi so luong dong thoi CO GIOI HAN.

    VI SAO KHONG DUNG BackgroundTasks CHO TUNG ANH: Starlette chay cac task nen
    lan luot, nen mot lo 10 anh mat gap 10 lan thoi gian mot anh.

    VI SAO KHONG CHAY HET SONG SONG: 10 loi goi Vision cung luc de cham tran
    quota va tao mot cu nhay chi phi. Gioi han so luong dong thoi lay phan lon
    toc do ma khong dap vao dich vu.

    `run_scan` da an toan khi chay dong thoi: no gianh ban quet bang mot lenh
    UPDATE co dieu kien `status='pending'`, nen hai luong khong the xu ly cung
    mot ban quet.
    """
    workers = max(1, min(config.batch_workers, len(scan_ids)))
    if workers == 1:
        for scan_id in scan_ids:
            run_scan(scan_id, config, session_factory)
        return

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_scan, sid, config, session_factory)
                   for sid in scan_ids]
        for future in futures:
            future.result()      # nem lai loi thay vi nuot im lang


def notify_completed(scan_id: str, grounding: dict, config: Settings,
                     session_factory) -> None:
    """Bao webhook rang ban quet da xong.

    Ban quet DA hoan tat truoc khi ham nay chay. Loi gui webhook khong duoc
    lam hong no, nen moi ngoai le deu bi nuot lai va chi ghi log.
    """
    if not getattr(config, "webhook_enabled", False):
        return
    try:
        from app.webhook import dispatch_scan_completed

        draft = grounding.get("draft") or {}
        dispatch_scan_completed(
            scan_id,
            {
                "card_language": draft.get("card_language", ""),
                "fields": draft.get("fields", {}),
                "confidence": (grounding.get("confidence") or {}).get("overall_score"),
            },
            config, session_factory,
        )
    except Exception:
        logging.getLogger(__name__).exception("Gui webhook that bai cho %s", scan_id)
