import json
import re
from datetime import datetime
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ai_helper import AI_GRAPH, WRITING_STYLE_RULES
from models import (
    ContextCategory,
    ContextItem,
    ContextItemCreate,
    ContextItemUpdate,
    ContextProfile,
    ContextSource,
    ContextSourceCreate,
    ContextSourceUpdate,
    ContextStats,
)


# ============================================================================
# Database CRUD Operations
# ============================================================================

def list_sources(conn, active_only: bool = False) -> list[ContextSource]:
    cursor = conn.cursor()
    query = "SELECT * FROM context_sources"
    params = []
    if active_only:
        query += " WHERE is_active = ?"
        params.append(True)
    query += " ORDER BY id DESC"
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    return [
        ContextSource(
            id=row["id"],
            title=row["title"],
            source_type=row["source_type"],
            content=row["content"],
            url=row["url"],
            is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in rows
    ]


def get_source(conn, source_id: int) -> Optional[ContextSource]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM context_sources WHERE id = ?", (source_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return ContextSource(
        id=row["id"],
        title=row["title"],
        source_type=row["source_type"],
        content=row["content"],
        url=row["url"],
        is_active=bool(row["is_active"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def create_source(conn, data: ContextSourceCreate) -> int:
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO context_sources (title, source_type, content, url, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.title.strip(),
            data.source_type,
            data.content.strip(),
            data.url.strip() if data.url else None,
            bool(data.is_active),
            now,
            now,
        ),
    )
    source_id = cursor.lastrowid
    conn.commit()
    return source_id


def update_source(conn, source_id: int, data: ContextSourceUpdate) -> Optional[ContextSource]:
    source = get_source(conn, source_id)
    if not source:
        return None
    now = datetime.now().isoformat()
    new_title = data.title.strip() if data.title is not None else source.title
    new_content = data.content.strip() if data.content is not None else source.content
    new_url = data.url.strip() if data.url is not None else source.url
    new_active = data.is_active if data.is_active is not None else source.is_active

    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE context_sources
        SET title = ?, content = ?, url = ?, is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_title, new_content, new_url, bool(new_active), now, source_id),
    )
    conn.commit()
    return get_source(conn, source_id)


def delete_source(conn, source_id: int) -> bool:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM context_sources WHERE id = ?", (source_id,))
    deleted = cursor.rowcount > 0 if hasattr(cursor, "rowcount") and cursor.rowcount is not None else True
    conn.commit()
    return deleted


def list_items(
    conn,
    category: Optional[str] = None,
    active_only: bool = False,
    query: Optional[str] = None,
) -> list[ContextItem]:
    cursor = conn.cursor()
    sql = "SELECT * FROM context_items WHERE 1=1"
    params = []
    if category and category != "all":
        sql += " AND category = ?"
        params.append(category)
    if active_only:
        sql += " AND is_active = ?"
        params.append(True)
    if query and query.strip():
        sql += " AND (title LIKE ? OR content LIKE ? OR tags LIKE ?)"
        like_param = f"%{query.strip()}%"
        params.extend([like_param, like_param, like_param])

    sql += " ORDER BY id DESC"
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    items = []
    for r in rows:
        tags = []
        if r["tags"]:
            try:
                tags = json.loads(r["tags"])
            except Exception:
                tags = [t.strip() for t in r["tags"].split(",") if t.strip()]
        items.append(
            ContextItem(
                id=r["id"],
                source_id=r["source_id"],
                category=r["category"],
                title=r["title"],
                content=r["content"],
                tags=tags if isinstance(tags, list) else [],
                is_active=bool(r["is_active"]),
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
        )
    return items


def get_item(conn, item_id: int) -> Optional[ContextItem]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM context_items WHERE id = ?", (item_id,))
    r = cursor.fetchone()
    if not r:
        return None
    tags = []
    if r["tags"]:
        try:
            tags = json.loads(r["tags"])
        except Exception:
            tags = [t.strip() for t in r["tags"].split(",") if t.strip()]
    return ContextItem(
        id=r["id"],
        source_id=r["source_id"],
        category=r["category"],
        title=r["title"],
        content=r["content"],
        tags=tags if isinstance(tags, list) else [],
        is_active=bool(r["is_active"]),
        created_at=str(r["created_at"]),
        updated_at=str(r["updated_at"]),
    )


def create_item(conn, data: ContextItemCreate) -> int:
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO context_items (source_id, category, title, content, tags, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data.source_id,
            data.category,
            data.title.strip(),
            data.content.strip(),
            json.dumps(data.tags or []),
            bool(data.is_active),
            now,
            now,
        ),
    )
    item_id = cursor.lastrowid
    conn.commit()
    return item_id


def update_item(conn, item_id: int, data: ContextItemUpdate) -> Optional[ContextItem]:
    item = get_item(conn, item_id)
    if not item:
        return None
    now = datetime.now().isoformat()
    new_category = data.category if data.category is not None else item.category
    new_title = data.title.strip() if data.title is not None else item.title
    new_content = data.content.strip() if data.content is not None else item.content
    new_tags = data.tags if data.tags is not None else item.tags
    new_active = data.is_active if data.is_active is not None else item.is_active

    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE context_items
        SET category = ?, title = ?, content = ?, tags = ?, is_active = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            new_category,
            new_title,
            new_content,
            json.dumps(new_tags or []),
            bool(new_active),
            now,
            item_id,
        ),
    )
    conn.commit()
    return get_item(conn, item_id)


def toggle_item(conn, item_id: int, is_active: Optional[bool] = None) -> Optional[ContextItem]:
    item = get_item(conn, item_id)
    if not item:
        return None
    now = datetime.now().isoformat()
    target_active = not item.is_active if is_active is None else is_active
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE context_items SET is_active = ?, updated_at = ? WHERE id = ?",
        (bool(target_active), now, item_id),
    )
    conn.commit()
    return get_item(conn, item_id)


def delete_item(conn, item_id: int) -> bool:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM context_items WHERE id = ?", (item_id,))
    deleted = cursor.rowcount > 0 if hasattr(cursor, "rowcount") and cursor.rowcount is not None else True
    conn.commit()
    return deleted


def get_profile(conn) -> Optional[ContextProfile]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM context_profiles ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return None
    differentiators = []
    target_roles = []
    stats = {}
    try:
        differentiators = json.loads(row["key_differentiators"])
    except Exception:
        pass
    try:
        target_roles = json.loads(row["target_roles"])
    except Exception:
        pass
    try:
        stats = json.loads(row["stats"])
    except Exception:
        pass

    return ContextProfile(
        id=row["id"],
        summary=row["summary"],
        key_differentiators=differentiators if isinstance(differentiators, list) else [],
        target_roles=target_roles if isinstance(target_roles, list) else [],
        stats=stats if isinstance(stats, dict) else {},
        updated_at=str(row["updated_at"]),
    )


def save_profile(
    conn,
    summary: str,
    key_differentiators: list[str],
    target_roles: list[str],
    stats: dict,
) -> ContextProfile:
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("SELECT id FROM context_profiles LIMIT 1")
    row = cursor.fetchone()
    if row:
        profile_id = row["id"]
        cursor.execute(
            """
            UPDATE context_profiles
            SET summary = ?, key_differentiators = ?, target_roles = ?, stats = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                summary.strip(),
                json.dumps(key_differentiators or []),
                json.dumps(target_roles or []),
                json.dumps(stats or {}),
                now,
                profile_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO context_profiles (summary, key_differentiators, target_roles, stats, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                summary.strip(),
                json.dumps(key_differentiators or []),
                json.dumps(target_roles or []),
                json.dumps(stats or {}),
                now,
            ),
        )
    conn.commit()
    return get_profile(conn)


def get_stats(conn) -> ContextStats:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM context_sources WHERE is_active = ?", (True,))
    sources_count = cursor.fetchone()["count"]

    cursor.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN is_active = ? THEN 1 ELSE 0 END) AS active FROM context_items",
        (True,),
    )
    item_counts = cursor.fetchone()
    total_items = item_counts["total"] or 0
    active_items = item_counts["active"] or 0

    cursor.execute("SELECT category, COUNT(*) AS count FROM context_items GROUP BY category")
    category_rows = cursor.fetchall()
    categories_breakdown = {r["category"]: r["count"] for r in category_rows}

    cursor.execute("SELECT title, content FROM context_items WHERE is_active = ?", (True,))
    active_rows = cursor.fetchall()
    total_chars = sum(len(r["title"] or "") + len(r["content"] or "") for r in active_rows)
    profile = get_profile(conn)
    if profile:
        total_chars += len(profile.summary)

    estimated_tokens = max(1, total_chars // 4) if total_chars > 0 else 0

    return ContextStats(
        total_sources=sources_count,
        total_items=total_items,
        active_items=active_items,
        categories_breakdown=categories_breakdown,
        estimated_tokens=estimated_tokens,
        last_processed_at=profile.updated_at if profile else None,
    )


# ============================================================================
# AI Knowledge Distillation Pipeline
# ============================================================================

DISTILLATION_SYSTEM_PROMPT = f"""You are a senior executive talent architect and deep intelligence analyst.
Your task is to ingest unstructured, multi-source raw candidate data (such as extensive background dumps, AI conversational transcripts, GitHub repositories, LinkedIn notes, portfolio narratives, project post-mortems, and technical war stories) and distill it into structured, atomized, verified knowledge cards and an executive persona.

{WRITING_STYLE_RULES}

OBJECTIVES:
1. Extract rich, factual, concrete evidence. Do not omit metrics, percentages, throughput numbers, system architectures, specific tools, or real outcomes.
2. Atomize the data into distinct, self-contained knowledge cards across these exact 6 categories:
   - "profile_persona": Core positioning, engineering/work philosophies, leadership style, communication nuance, unique personal value proposition.
   - "experience_project": Specific projects, side-projects, open-source work, unlisted initiatives, architectural challenges, and systems built.
   - "achievement_metric": Hard numbers and verifiable accomplishments (e.g. latency reduced from 800ms to 45ms, scaled to 1M users, generated $500k ARR, zero downtime migration).
   - "skills_arsenal": Distinct technical competencies, frameworks, patterns, and paradigms with practical context of how they were applied.
   - "education_credential": Academic degrees, notable publications, patents, specialized certifications, and deep courses.
   - "proof_link": Verifiable links (GitHub profiles/repos, personal websites, live production apps, published articles) with a summary of what they prove.
3. Every card must have:
   - "title": Concise, highly descriptive label (e.g. "Distributed Stream Processing Pipeline", "Zero-Downtime Database Migration").
   - "content": 2-4 dense sentences explaining the context, challenge, exact technologies, and measurable results.
   - "tags": 2-6 lower-case keywords (e.g. ["python", "kafka", "distributed-systems", "performance"]).
4. Formulate a comprehensive 3-4 sentence "profile_summary" capturing the candidate's holistic edge, a list of 3-5 "key_differentiators", and 2-4 "target_roles".

Be truthful: never invent claims not present in the supplied source materials.
Return ONLY valid JSON matching the schema.
"""

DISTILLATION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "profile_summary": {"type": "string"},
        "key_differentiators": {
            "type": "array",
            "items": {"type": "string"},
        },
        "target_roles": {
            "type": "array",
            "items": {"type": "string"},
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "profile_persona",
                            "experience_project",
                            "achievement_metric",
                            "skills_arsenal",
                            "education_credential",
                            "proof_link",
                        ],
                    },
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["category", "title", "content", "tags"],
            },
        },
    },
    "required": ["profile_summary", "key_differentiators", "target_roles", "items"],
}


def synthesize_context(
    conn,
    provider: str = "gemini",
    additional_notes: Optional[str] = None,
    replace_existing: bool = False,
) -> dict:
    """Run AI knowledge distillation on all active sources in the Context Vault."""
    sources = list_sources(conn, active_only=True)
    if not sources:
        raise ValueError(
            "No active context sources found. Please add at least one context source (text dump, link, or notes) first."
        )

    source_blocks = []
    for i, s in enumerate(sources, 1):
        block = f"--- SOURCE {i}: {s.title} ({s.source_type.upper()}) ---\n"
        if s.url:
            block += f"URL: {s.url}\n"
        block += f"CONTENT:\n{s.content}\n"
        source_blocks.append(block)

    user_message = "CANDIDATE SOURCE MATERIALS:\n\n" + "\n\n".join(source_blocks)
    if additional_notes:
        user_message += f"\n\nADDITIONAL INSTRUCTIONS OR EMPHASIS:\n{additional_notes}"

    state = AI_GRAPH.invoke(
        {
            "provider": provider,
            "messages": [
                SystemMessage(content=DISTILLATION_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
            "schema": DISTILLATION_OUTPUT_SCHEMA,
            "max_tokens": 8000,
        }
    )

    result = state.get("result")
    if not isinstance(result, dict) or "items" not in result:
        raise ValueError("AI provider failed to distill structured context items.")

    items = result.get("items", [])
    profile_summary = result.get("profile_summary", "").strip()
    key_differentiators = result.get("key_differentiators", [])
    target_roles = result.get("target_roles", [])

    cursor = conn.cursor()
    if replace_existing:
        cursor.execute("DELETE FROM context_items")
        conn.commit()

    now = datetime.now().isoformat()
    inserted_count = 0
    categories_breakdown = {}

    for itm in items:
        cat = itm.get("category", "experience_project")
        title = itm.get("title", "").strip()
        content = itm.get("content", "").strip()
        tags = itm.get("tags", [])
        if not title or not content:
            continue

        cursor.execute(
            """
            INSERT INTO context_items (source_id, category, title, content, tags, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (None, cat, title, content, json.dumps(tags), True, now, now),
        )
        inserted_count += 1
        categories_breakdown[cat] = categories_breakdown.get(cat, 0) + 1

    conn.commit()

    save_profile(
        conn,
        summary=profile_summary,
        key_differentiators=key_differentiators,
        target_roles=target_roles,
        stats={"extracted_count": inserted_count, "categories": categories_breakdown},
    )

    return {
        "extracted_items_count": inserted_count,
        "profile_summary": profile_summary,
        "categories_breakdown": categories_breakdown,
    }


# ============================================================================
# Smart Context Retrieval & Assembling Engine
# ============================================================================

def _tokenize(text: str) -> set[str]:
    """Extract clean lowercase keywords of length > 2."""
    if not text:
        return set()
    cleaned = re.sub(r"[^a-zA-Z0-9_\-\+\#]", " ", text.lower())
    return {w for w in cleaned.split() if len(w) > 2}


def _score_item(
    item: ContextItem,
    query_tokens: set[str],
) -> float:
    """Calculate relevance score of a context item against target query tokens."""
    if not query_tokens:
        if item.category == "profile_persona":
            return 10.0
        if item.category == "achievement_metric":
            return 8.0
        if item.category == "experience_project":
            return 7.0
        if item.category == "skills_arsenal":
            return 6.0
        return 5.0

    score = 0.0

    if item.category == "profile_persona":
        score += 2.0
    elif item.category == "achievement_metric":
        score += 3.0

    for tag in item.tags:
        tag_lower = tag.lower()
        if tag_lower in query_tokens:
            score += 5.0
        else:
            for qt in query_tokens:
                if qt in tag_lower or tag_lower in qt:
                    score += 2.5
                    break

    title_tokens = _tokenize(item.title)
    common_title = title_tokens.intersection(query_tokens)
    score += len(common_title) * 3.0

    content_tokens = _tokenize(item.content)
    common_content = content_tokens.intersection(query_tokens)
    score += len(common_content) * 1.0

    return score


def assemble_context(
    conn,
    target_role: Optional[str] = None,
    job_description: Optional[str] = None,
    company: Optional[str] = None,
    max_items: int = 15,
) -> str:
    """Intelligently assemble relevant candidate context into a bounded markdown block."""
    items = list_items(conn, active_only=True)
    profile = get_profile(conn)

    if not items and not profile:
        return ""

    query_text = ""
    if target_role:
        query_text += f" {target_role}"
    if job_description:
        query_text += f" {job_description}"
    if company:
        query_text += f" {company}"

    query_tokens = _tokenize(query_text)

    scored_items = [(item, _score_item(item, query_tokens)) for item in items]
    scored_items.sort(key=lambda x: x[1], reverse=True)

    selected_items: list[ContextItem] = []
    seen_ids = set()

    for itm, _ in scored_items:
        if itm.category == "profile_persona" and itm.id not in seen_ids:
            selected_items.append(itm)
            seen_ids.add(itm.id)
            break

    for itm, score in scored_items:
        if len(selected_items) >= max_items:
            break
        if itm.id not in seen_ids:
            selected_items.append(itm)
            seen_ids.add(itm.id)

    categorized: dict[str, list[ContextItem]] = {
        "profile_persona": [],
        "achievement_metric": [],
        "experience_project": [],
        "skills_arsenal": [],
        "education_credential": [],
        "proof_link": [],
    }
    for itm in selected_items:
        if itm.category in categorized:
            categorized[itm.category].append(itm)
        else:
            categorized.setdefault("experience_project", []).append(itm)

    lines = ["=== CANDIDATE VERIFIED CONTEXT VAULT (AUTHENTIC BACKGROUND DATA) ==="]

    if profile and profile.summary:
        lines.append(f"EXECUTIVE SUMMARY & POSITIONING:\n{profile.summary}")
        if profile.key_differentiators:
            lines.append("KEY DIFFERENTIATORS:\n" + "\n".join(f"- {d}" for d in profile.key_differentiators))

    if categorized["profile_persona"]:
        lines.append("\nPERSONA & WORKING PRINCIPLES:")
        for itm in categorized["profile_persona"]:
            lines.append(f"- **{itm.title}**: {itm.content}")

    if categorized["achievement_metric"]:
        lines.append("\nKEY VERIFIED ACHIEVEMENTS & SCALE METRICS:")
        for itm in categorized["achievement_metric"]:
            tags_str = f" [tags: {', '.join(itm.tags)}]" if itm.tags else ""
            lines.append(f"- **{itm.title}**: {itm.content}{tags_str}")

    if categorized["experience_project"]:
        lines.append("\nDEEP TECHNICAL WORK & UNLISTED PROJECTS:")
        for itm in categorized["experience_project"]:
            tags_str = f" [tech: {', '.join(itm.tags)}]" if itm.tags else ""
            lines.append(f"- **{itm.title}**: {itm.content}{tags_str}")

    if categorized["skills_arsenal"]:
        lines.append("\nTECHNICAL ARSENAL & PRACTICAL PROFICIENCIES:")
        for itm in categorized["skills_arsenal"]:
            lines.append(f"- **{itm.title}**: {itm.content}")

    if categorized["proof_link"]:
        lines.append("\nPORTFOLIO, REPOSITORIES & REPUTATION LINKS:")
        for itm in categorized["proof_link"]:
            lines.append(f"- **{itm.title}**: {itm.content}")

    if categorized["education_credential"]:
        lines.append("\nCREDENTIALS & DEEP SPECIALIZATIONS:")
        for itm in categorized["education_credential"]:
            lines.append(f"- **{itm.title}**: {itm.content}")

    lines.append("=== END CANDIDATE CONTEXT VAULT ===\n")

    return "\n".join(lines)
