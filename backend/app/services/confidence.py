"""Confidence Scoring Agent: Calculates field-level and scan-level confidence."""
from __future__ import annotations

import logging
import re
from typing import Any

from app.services import languages

logger = logging.getLogger(__name__)

class ConfidenceAgent:
    """Evaluates the confidence of extracted information."""
    
    def __init__(self):
        self.email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
        
    def evaluate_field(self, field_name: str, item: dict, scan_langs: list[str]) -> dict:
        """Calculate confidence for a single field."""
        score = 1.0
        reasons = []
        
        verdict = item.get("grounding_verdict", "exact")
        if verdict == "fuzzy":
            score -= 0.3
            reasons.append("fuzzy_match")
        elif verdict == "unverified":
            score -= 0.8
            reasons.append("unverified")
            
        value = item.get("value", "")

        # Tin hieu 2: do tin cay cua chinh OCR, neu nha cung cap co tra ve.
        # Truoc day tin hieu nay bi bo qua du Vision van cung cap no.
        ocr_conf = item.get("ocr_confidence")
        if isinstance(ocr_conf, (int, float)) and ocr_conf < 0.8:
            score -= 0.2
            reasons.append("low_ocr_confidence")

        # Tin hieu 3: ngon ngu.
        # Dai Unicode nam o `languages.py` - ban cu viet tay o day va BO SOT
        # Hangul, nen ten tieng Han khong duoc nhan la CJK va tin hieu nay im
        # lang khong bao gio kich hoat cho the tieng Han.
        if scan_langs and field_name in ("full_names", "company_names", "addresses"):
            if not languages.matches_hint(value, scan_langs):
                score -= 0.15
                reasons.append("language_mismatch")

        # Field-specific heuristics
        if field_name == "emails":
            if not self.email_regex.match(value):
                score -= 0.5
                reasons.append("invalid_email_format")
        elif field_name == "phones":
            digits_only = "".join(filter(str.isdigit, value))
            if len(digits_only) < 7:
                score -= 0.4
                reasons.append("phone_too_short")
                
        # Bounding limits
        score = max(0.0, min(1.0, score))
        return {"score": round(score, 2), "reasons": reasons}

    @staticmethod
    def _domain_of(email: str) -> str:
        return email.rpartition("@")[2].strip().lower().removeprefix("www.")

    def _cross_field(self, fields: dict, field_scores: dict) -> float:
        """Dieu chinh diem email theo su nhat quan voi website tren the.

        Tra ve tong muc dieu chinh de nguoi goi cong vao `total_score`, giu cho
        diem trung binh tong the van khop voi diem tung dong.
        """
        sites = {
            (item.get("website_domain") or "").removeprefix("www.")
            for item in fields.get("websites", [])
            if item.get("website_domain")
        }
        if not sites:
            return 0.0

        delta = 0.0
        for index, item in enumerate(fields.get("emails", [])):
            if item.get("source") == "user":
                continue
            domain = self._domain_of(item.get("value", ""))
            if not domain:
                continue

            matched = any(domain == site or domain.endswith("." + site)
                          or site.endswith("." + domain) for site in sites)
            if matched:
                adjust, reason = 0.1, "domain_matches_website"
            elif item.get("is_free_email_domain"):
                continue                       # hop le, khong thuong khong phat
            else:
                adjust, reason = -0.1, "domain_differs_from_website"

            before = item.get("confidence_score", 1.0)
            after = round(max(0.0, min(1.0, before + adjust)), 2)
            item["confidence_score"] = after
            item.setdefault("confidence_reasons", []).append(reason)
            if index < len(field_scores.get("emails", [])):
                entry = field_scores["emails"][index]
                entry["score"] = after
                entry.setdefault("reasons", []).append(reason)
            delta += after - before
        return delta

    def evaluate_scan(self, draft: dict, scan_langs: list[str]) -> dict:
        """Calculate confidence for the entire scan."""
        fields = draft.get("fields", {})
        
        field_scores = {}
        total_score = 0
        count = 0
        
        for field_name, items in fields.items():
            field_scores[field_name] = []
            for item in items:
                eval_res = self.evaluate_field(field_name, item, scan_langs)
                # Assign back to item
                item["confidence_score"] = eval_res["score"]
                item["confidence_reasons"] = eval_res["reasons"]
                
                # Kem gia tri de noi khac doi chieu duoc theo gia tri thay vi
                # theo vi tri - vi tri doi thi diem se bi gan nham dong.
                field_scores[field_name].append(
                    {**eval_res, "value": item.get("value")}
                )
                total_score += eval_res["score"]
                count += 1
                
        # Tin hieu 4: nhat quan giua cac truong.
        # Email co ten mien trung voi website in tren the la bang chung noi tai
        # rang ca hai deu duoc doc dung. Nguoc lai, email cong ty tro toi mot
        # ten mien khac han website la dau hieu it nhat mot trong hai bi doc sai.
        # Email dich vu cong cong (gmail...) KHONG bi phat - rat nhieu the that
        # dung email ca nhan mot cach hoan toan hop le.
        total_score += self._cross_field(fields, field_scores)

        avg_score = total_score / count if count > 0 else 0.0
        
        # Critical missing fields penalty
        missing_critical = []
        if not fields.get("full_names"):
            avg_score -= 0.2
            missing_critical.append("missing_name")
        if not fields.get("company_names"):
            avg_score -= 0.2
            missing_critical.append("missing_company")
            
        overall_score = max(0.0, min(1.0, avg_score))
        
        return {
            "overall_score": round(overall_score, 2),
            "missing_critical": missing_critical,
            "field_scores": field_scores
        }
