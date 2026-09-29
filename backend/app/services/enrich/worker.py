"""Independent research job; never writes scan status or OCR/draft values."""
import time
from urllib.parse import urlsplit

from sqlalchemy import select, update

from app.models import Enrichment, EnrichmentJob, utcnow
from app.services.enrich.discover import seed_url, identity_matches, candidate_pages
from app.services.enrich.fetcher import SafeFetcher, FetchError
from app.services.enrich.summarize import GeminiSummarizer, validate_claims, SummaryError, tim_website


def run_enrichment(job_id: str, config, session_factory):
    with session_factory() as db:
        claimed = db.execute(update(EnrichmentJob).where(EnrichmentJob.id == job_id, EnrichmentJob.status == "pending")
                             .values(status="processing"))
        db.commit()
        if claimed.rowcount != 1:
            return
        job = db.get(EnrichmentJob, job_id)
        snapshot = job.snapshot
        org_id = job.organization_id
    started = time.perf_counter()
    pages, outcomes, claims, metadata = [], [], [], {}
    reason = None
    summarizer = None
    try:
        url, source = seed_url(snapshot)
        names = snapshot["fields"].get("company_names", [])
        if not url and names and config.enrich_enabled:
            # Khong co website hay email cong ty: tim website tu TEN doanh
            # nghiep. Trang tim duoc van phai qua moi phep kiem ben duoi.
            url = tim_website(names[0]["value"], config)
            source = "web_search" if url else "website_not_found"
        metadata["discovery_source"] = source
        if snapshot.get("research_input"):
            metadata["research_input"] = snapshot["research_input"]
        if not config.enrich_enabled:
            reason = "ENRICH_DISABLED"
        elif not url:
            reason = "NO_DOMAIN_ON_CARD"
        else:
            fetcher = SafeFetcher(config)
            homepage = fetcher.fetch(url)
            pages.append(homepage)
            matched = identity_matches(snapshot, homepage.text)
            outcomes.append({"url": homepage.url, "status": "fetched"})
            for candidate in candidate_pages(homepage, min(max(config.enrich_max_pages, 1), 5)):
                try:
                    page = fetcher.fetch(candidate)
                    if page.url in {p.url for p in pages}:
                        continue
                    # Cross-domain redirects must independently match the company.
                    if urlsplit(page.url).hostname != urlsplit(homepage.url).hostname and not identity_matches(snapshot, page.text):
                        outcomes.append({"url": page.url, "status": "IDENTITY_MISMATCH"})
                        continue
                    pages.append(page)
                    outcomes.append({"url": page.url, "status": "fetched"})
                except FetchError as exc:
                    outcomes.append({"url": candidate, "status": exc.code})
            metadata["identity_verified"] = matched
            summarizer = GeminiSummarizer(config)
            proposed = summarizer.extract(pages)
            claims, rejected = validate_claims(proposed, pages, matched)
            metadata.update(model=config.gemini_model, rejected_claims=rejected)
            if not claims:
                reason = "NO_VERIFIABLE_CLAIMS"
            elif not matched:
                reason = "IDENTITY_UNVERIFIED"
    except FetchError as exc:
        reason = exc.code
    except SummaryError as exc:
        reason = str(exc)
    except Exception:
        reason = "ENRICH_FAILED"
    finally:
        if summarizer:
            try:
                summarizer.close()
            except Exception:
                pass
    metadata["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    if config.agent_enabled:
        from app.services.agent_orchestrator import AgenticOrchestrator, Action
        decision = AgenticOrchestrator()
        decision.record_decision("enrichment_agent", Action.ESCALATE if reason else Action.PROCEED,
                                 "Cần tra cứu thủ công hoặc kiểm tra nguồn." if reason else "Đã có thông tin đối chiếu nguồn.", 0.0)
        metadata["agent_decisions"] = decision.get_decisions_log()
        if reason:
            names = snapshot["fields"].get("company_names", [])
            metadata["manual_search_query"] = (names[0]["value"][:300] + " official website") if names else None
    # Store the exact text inspected by the validator for later evidence audits.
    metadata["sources"] = [{"url": page.url, "title": page.title, "text": page.text,
                             "fetched_at": page.fetched_at} for page in pages]
    existing_attributes = {claim["attribute"] for claim in claims}
    for attribute in ("industry", "company_size", "products_services"):
        if attribute not in existing_attributes:
            claims.append({"attribute": attribute, "value": None, "status": "not_found"})
    with session_factory() as db:
        job = db.get(EnrichmentJob, job_id)
        records = [Enrichment(organization_id=org_id, **claim) for claim in claims]
        db.add_all(records)
        db.flush()
        job.result_ids = [record.id for record in records]
        job.reason, job.pages, job.metadata_json = reason, outcomes, metadata
        job.status, job.completed_at = "done", utcnow()
        db.commit()


def job_result(db, job):
    if job is None:
        return None
    records = db.scalars(select(Enrichment).where(Enrichment.id.in_(job.result_ids))).all() if job.result_ids else []
    return {"id": job.id, "organization_id": job.organization_id, "scan_id": job.scan_id,
            "draft_revision": job.draft_revision, "status": job.status, "attempts": job.attempts,
            "reason": job.reason, "pages": job.pages, "completed_at": job.completed_at,
            "metadata": {key: value for key, value in job.metadata_json.items() if key != "sources"},
            "enrichments": [{"id": row.id, "attribute": row.attribute, "value": row.value,
                "source_url": row.source_url, "source_title": row.source_title,
                "evidence_snippet": row.evidence_snippet, "fetched_at": row.fetched_at,
                "status": row.status, "reviewed": row.reviewed,
                "decision": job.decisions.get(row.id, "pending")} for row in records]}
