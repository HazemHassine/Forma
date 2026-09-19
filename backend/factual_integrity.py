"""Deterministic factual-integrity checks for generated resume edits.

Prompts can request truthful output, but this module is the enforcement boundary.
Every changed field must cite existing evidence and pass entity, metric, URL, and
semantic-strength checks before it can be merged into a resume.
"""

from __future__ import annotations

import copy
import re
from typing import Any


NUMBER_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?:%|\+)?")
URL_RE = re.compile(r"https?://[^\s)\]}>,]+", re.IGNORECASE)
WORD_RE = re.compile(r"[a-z0-9][a-z0-9+#.-]*", re.IGNORECASE)
CLAUSE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")

EXACT_CAPABILITY_TERMS = (
    "multi-agent",
    "multi agent",
    "multiagent",
    "autonomous",
    "autonomously",
    "rollback",
    "rollbacks",
    "zero-downtime",
    "zero downtime",
)
DELIVERY_TERMS = (
    "implemented", "deployed", "launched", "delivered", "production-ready",
    "built", "created", "shipped", "released", "operated",
)
DELIVERY_EVIDENCE = (
    "implemented", "deployed", "launched", "delivered", "built", "created",
    "shipped", "released", "operated", "maintained", "production",
)
PLANNING_TERMS = ("planned", "proposed", "roadmap", "intended", "future", "to be")
SENSITIVE_EXACT_TERMS = (
    "enterprise-wide", "enterprise", "large-scale", "high-throughput", "global",
    "company-wide", "organization-wide", "mission-critical", "fault-tolerant",
    "real-time", "expert", "expertise", "advanced proficiency", "led", "managed",
    "owned", "architected", "directed", "hundreds", "thousands", "millions", "dozens",
)
NAMED_TERM_RE = re.compile(r"\b[A-Z][A-Za-z0-9+#.-]{1,}\b")
ALLOWED_SENTENCE_TERMS = {
    "Built", "Created", "Developed", "Delivered", "Improved", "Reduced", "Increased",
    "Designed", "Implemented", "Maintained", "Analyzed", "Researched", "Supported",
    "Engineered", "Handled", "Processed", "Optimized", "Automated", "Coordinated",
    "Assisted", "Authored", "Collaborated", "Contributed", "Experienced", "Mapped",
    "Partnered", "Participated", "Programmed", "Produced", "Reconstructed", "Structured",
    "Trained", "Translated",
    "Engineering", "Software", "Systems", "Data", "Technical", "Professional",
}
ALLOWED_SENTENCE_WORDS = {term.lower() for term in ALLOWED_SENTENCE_TERMS}
STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "of",
    "on", "or", "the", "to", "with", "using", "used", "that", "this", "their",
    "its", "through", "across", "while", "within", "over", "under",
}


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _tokens(value: str) -> set[str]:
    tokens = {token.lower().strip(".-") for token in WORD_RE.findall(value or "")}
    return {token for token in tokens if token and token not in STOPWORDS}


def _entry_key(kind: str, entry: dict, index: int) -> str:
    if kind == "work_experience":
        return f"{entry.get('company', '')}|{entry.get('role', '')}".lower()
    if kind == "projects":
        return str(entry.get("name", "")).lower()
    if kind == "research":
        return str(entry.get("title", "")).lower()
    return f"{kind}:{index}"


def build_resume_evidence(resume: dict) -> list[dict]:
    evidence: list[dict] = []

    about = str(resume.get("about_me") or "").strip()
    if about:
        evidence.append({
            "id": "resume:about_me",
            "text": about,
            "subject_type": "profile",
            "subject_key": "candidate",
        })

    for kind in ("work_experience", "projects", "research"):
        for index, entry in enumerate(resume.get(kind, []) or []):
            subject_key = _entry_key(kind, entry, index)
            parts: list[str] = []
            for key in (
                "company", "role", "dates", "name", "type", "stack", "extra_info",
                "title", "institution", "focus", "description",
            ):
                value = entry.get(key)
                if value:
                    parts.append(str(value))
            parts.extend(str(item) for item in entry.get("bullets", []) or [])
            evidence.append({
                "id": f"resume:{kind}:{index}",
                "text": "\n".join(parts),
                "subject_type": kind,
                "subject_key": subject_key,
            })
    return evidence


def field_subject(resume: dict, path: str) -> tuple[str, str]:
    parts = path.split(".")
    if path == "about_me":
        return "profile", "candidate"
    if len(parts) >= 2 and parts[0] in {"work_experience", "projects", "research"}:
        kind = parts[0]
        try:
            index = int(parts[1])
            entry = (resume.get(kind) or [])[index]
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Unknown resume field path: {path}") from exc
        return kind, _entry_key(kind, entry, index)
    return "profile", "candidate"


def _validate_text(
    *,
    original: str,
    proposed: str,
    path: str,
    evidence_ids: list[str],
    evidence_map: dict[str, dict],
    subject: tuple[str, str],
    trust_original: bool = True,
) -> tuple[bool, str]:
    if proposed.strip() == original.strip():
        return True, "unchanged"
    if not evidence_ids:
        return False, "missing_evidence"

    cited = []
    for evidence_id in evidence_ids:
        evidence = evidence_map.get(evidence_id)
        if not evidence:
            return False, f"unknown_evidence:{evidence_id}"
        ev_subject = (evidence.get("subject_type"), evidence.get("subject_key"))
        if subject[0] != "profile":
            if ev_subject[0] not in {None, "profile", subject[0]}:
                return False, f"wrong_subject:{evidence_id}"
            if ev_subject[0] == subject[0] and ev_subject[1] and ev_subject[1] != subject[1]:
                return False, f"wrong_subject:{evidence_id}"
        cited.append(evidence)

    support_parts = [str(item.get("text") or "") for item in cited]
    if trust_original:
        support_parts.insert(0, original)
    support = "\n".join(support_parts)
    support_norm = _norm(support)
    proposed_norm = _norm(proposed)

    unsupported_numbers = sorted(set(NUMBER_RE.findall(proposed)) - set(NUMBER_RE.findall(support)))
    if unsupported_numbers:
        return False, f"unsupported_metric:{','.join(unsupported_numbers)}"

    unsupported_urls = sorted(set(URL_RE.findall(proposed)) - set(URL_RE.findall(support)))
    if unsupported_urls:
        return False, "unsupported_link"

    for term in EXACT_CAPABILITY_TERMS:
        if term in proposed_norm and term not in support_norm:
            return False, f"unsupported_capability:{term.replace(' ', '_')}"

    for term in SENSITIVE_EXACT_TERMS:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", proposed_norm) and not re.search(
            rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", support_norm
        ):
            return False, f"unsupported_sensitive_term:{term.replace(' ', '_')}"

    support_lower = support.lower()
    for term in NAMED_TERM_RE.findall(proposed):
        if term.lower() in ALLOWED_SENTENCE_WORDS or term.lower() in STOPWORDS:
            continue
        if term.lower() not in support_lower:
            return False, f"unsupported_named_term:{term}"

    if any(term in proposed_norm for term in DELIVERY_TERMS):
        original_norm = _norm(original)
        verified_delivery_update = any(
            str(item.get("id", "")).startswith("vault:")
            and any(term in _norm(item.get("text", "")) for term in DELIVERY_EVIDENCE)
            for item in cited
        )
        if any(term in original_norm for term in PLANNING_TERMS) and not verified_delivery_update:
            return False, "planned_work_presented_as_delivered"

    proposed_tokens = _tokens(proposed)
    support_tokens = _tokens(support)
    if proposed_tokens:
        overlap = len(proposed_tokens & support_tokens) / len(proposed_tokens)
        if overlap < 0.20:
            return False, "insufficient_evidence_overlap"

    return True, "supported"


def validate_resume_edits(
    original: dict,
    model_resume: dict,
    claim_evidence: dict[str, list[str]],
    vault_evidence: list[dict] | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    """Merge only supported model edits and return accepted/rejected audit records."""
    final_resume = copy.deepcopy(original)
    all_evidence = build_resume_evidence(original) + list(vault_evidence or [])
    evidence_map = {item["id"]: item for item in all_evidence}
    audit: list[dict] = []
    blocked: list[dict] = []

    def consider(path: str, original_text: str, proposed_text: Any, assign) -> None:
        if proposed_text is None:
            return
        proposed = str(proposed_text).strip()
        if not proposed or proposed == str(original_text).strip():
            return
        evidence_ids = claim_evidence.get(path, [])
        accepted = True
        reason = "supported"
        for clause in [part.strip() for part in CLAUSE_SPLIT_RE.split(proposed) if part.strip()]:
            clause_accepted, clause_reason = _validate_text(
                original=str(original_text), proposed=clause, path=path,
                evidence_ids=evidence_ids, evidence_map=evidence_map,
                subject=field_subject(original, path),
            )
            if not clause_accepted:
                accepted = False
                reason = clause_reason
                break
        record = {
            "field_path": path,
            "proposed_text": proposed,
            "evidence_ids": evidence_ids,
            "status": "accepted" if accepted else "blocked",
            "reason": reason,
        }
        audit.append(record)
        if accepted:
            assign(proposed)
        else:
            blocked.append(record)

    consider(
        "about_me", original.get("about_me", ""), model_resume.get("about_me"),
        lambda value: final_resume.__setitem__("about_me", value),
    )

    for index, entry in enumerate(original.get("work_experience", []) or []):
        candidate = (model_resume.get("work_experience") or [])
        if index >= len(candidate) or not isinstance(candidate[index], dict):
            continue
        proposed_bullets = candidate[index].get("bullets")
        if not isinstance(proposed_bullets, list) or len(proposed_bullets) != len(entry.get("bullets", [])):
            if proposed_bullets is not None:
                blocked.append({"field_path": f"work_experience.{index}.bullets", "status": "blocked", "reason": "bullet_count_mismatch"})
            continue
        for bullet_index, original_bullet in enumerate(entry.get("bullets", [])):
            path = f"work_experience.{index}.bullets.{bullet_index}"
            consider(
                path, original_bullet, proposed_bullets[bullet_index],
                lambda value, i=index, j=bullet_index: final_resume["work_experience"][i]["bullets"].__setitem__(j, value),
            )

    for index, entry in enumerate(original.get("projects", []) or []):
        candidate = model_resume.get("projects") or []
        if index >= len(candidate) or not isinstance(candidate[index], dict):
            continue
        proposed_entry = candidate[index]
        consider(
            f"projects.{index}.description", entry.get("description", ""), proposed_entry.get("description"),
            lambda value, i=index: final_resume["projects"][i].__setitem__("description", value),
        )
        proposed_bullets = proposed_entry.get("bullets")
        if isinstance(proposed_bullets, list) and len(proposed_bullets) == len(entry.get("bullets", [])):
            for bullet_index, original_bullet in enumerate(entry.get("bullets", [])):
                path = f"projects.{index}.bullets.{bullet_index}"
                consider(
                    path, original_bullet, proposed_bullets[bullet_index],
                    lambda value, i=index, j=bullet_index: final_resume["projects"][i]["bullets"].__setitem__(j, value),
                )
        elif proposed_bullets is not None:
            blocked.append({"field_path": f"projects.{index}.bullets", "status": "blocked", "reason": "bullet_count_mismatch"})

    for index, entry in enumerate(original.get("research", []) or []):
        candidate = model_resume.get("research") or []
        if index < len(candidate) and isinstance(candidate[index], dict):
            consider(
                f"research.{index}.description", entry.get("description", ""), candidate[index].get("description"),
                lambda value, i=index: final_resume["research"][i].__setitem__("description", value),
            )

    return final_resume, audit, blocked


def validate_suggestion(
    current_content: str,
    suggestion: str,
    field_path: str,
    evidence_ids: list[str],
    evidence: list[dict],
    subject: tuple[str, str] = ("profile", "candidate"),
) -> tuple[str, list[dict]]:
    evidence_map = {item["id"]: item for item in evidence}
    accepted, reason = _validate_text(
        original=current_content,
        proposed=suggestion,
        path=field_path,
        evidence_ids=evidence_ids,
        evidence_map=evidence_map,
        subject=subject,
        trust_original=False,
    )
    audit = [{
        "field_path": field_path,
        "proposed_text": suggestion,
        "evidence_ids": evidence_ids,
        "status": "accepted" if accepted else "blocked",
        "reason": reason,
    }]
    return (suggestion if accepted else current_content), audit
