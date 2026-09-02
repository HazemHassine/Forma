import json
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from ai_helper import AI_GRAPH


CRITIC_SYSTEM_PROMPT = """You are a rigorous, no-nonsense technical hiring manager and executive resume reviewer.
Your role is to identify every weakness, flaw, and missed opportunity in a candidate's CV so they can fix it before submitting applications.

CRITIQUE CRITERIA:
1. Impact & Quantifiability:
   - Every experience and project bullet should demonstrate results and scale, not merely daily responsibilities.
   - Flag bullets that start with passive duty descriptions ("Responsible for", "Helped with", "Worked on", "Assisted in", "Participated in").
   - Expect outcomes, metrics, percentages, throughput, latency reductions, team size, or concrete deliverables.

2. Brevity & Density:
   - Bullets should be punchy and readable in 1-2 lines.
   - Flag wordy phrasing, run-on clauses, and bloated explanations.
   - Ensure the About Me summary is concise (2-4 sentences max) and direct.

3. Style & Tone:
   - Strictly flag corporate cliches and empty buzzwords: "passionate", "motivated", "driven", "results-oriented", "synergized", "spearheaded", "cutting-edge", "innovative", "dynamic", "team player", "self-starter".
   - Flag repetitive verbs (e.g., starting multiple bullets in the same section with "Developed" or "Built").
   - Eliminate em dashes (—); enforce clean punctuation (commas, periods, semicolons).

4. Structure & Balance:
   - Check section hierarchy, role date clarity, and balance between recent and older experiences.
   - Check if skills are cleanly categorized (e.g. Languages, Frameworks, Cloud, Databases) rather than an unstructured keyword dump.
   - Check that personal contact info is complete and professional.

5. ATS & Role Fit:
   - If a target role or job description is provided, identify key requirements that are unevidenced or under-emphasized in the CV.
   - Check that technical skills mentioned in bullets are backed by real context.

ISSUE SEVERITY GUIDELINES:
- critical: Serious flaws that significantly lower callback rates (e.g., passive task lists with zero outcomes, buzzword-heavy summaries, unreadable sentence fragments).
- warning: Noticeable weaknesses that reduce competitiveness (e.g., missing metrics where obvious, weak opening verbs, repetitive phrasing).
- suggestion: Refinements that elevate polish and impact.

FOR EVERY ISSUE:
- "problem": Plain statement of what is wrong.
- "why_it_hurts": Clear recruiter/hiring manager perspective on why this harms the candidate.
- "original_text": The exact text excerpt from the CV.
- "suggested_fix": Concrete, professional rewrite that directly fixes the problem without inventing unverified facts.

TONE:
- Direct, clear, and analytical.
- No marketing jargon, no cheerleading, no generic fluff.
"""

CRITIQUE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "integer"},
        "verdict": {"type": "string"},
        "summary": {"type": "string"},
        "category_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["impact", "brevity", "style", "structure", "ats"],
                    },
                    "label": {"type": "string"},
                    "score": {"type": "integer"},
                    "summary": {"type": "string"},
                },
                "required": ["category", "label", "score", "summary"],
            },
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
        },
        "critical_count": {"type": "integer"},
        "warning_count": {"type": "integer"},
        "suggestion_count": {"type": "integer"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "section": {"type": "string"},
                    "location_label": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "warning", "suggestion"],
                    },
                    "category": {
                        "type": "string",
                        "enum": ["impact", "brevity", "style", "structure", "ats"],
                    },
                    "problem": {"type": "string"},
                    "why_it_hurts": {"type": "string"},
                    "original_text": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": [
                    "id",
                    "section",
                    "location_label",
                    "severity",
                    "category",
                    "problem",
                    "why_it_hurts",
                    "original_text",
                    "suggested_fix",
                ],
            },
        },
    },
    "required": [
        "overall_score",
        "verdict",
        "summary",
        "category_scores",
        "strengths",
        "critical_count",
        "warning_count",
        "suggestion_count",
        "issues",
    ],
}


def critique_cv(
    resume_data: dict,
    target_role: Optional[str] = None,
    job_description: Optional[str] = None,
    instructions: Optional[str] = None,
    provider: str = "gemini",
) -> dict:
    """Analyze resume_data and produce a structured critique report."""
    context_lines = []
    if target_role:
        context_lines.append(f"TARGET ROLE: {target_role}")
    if job_description:
        context_lines.append(f"TARGET JOB POST:\n{job_description}")
    if instructions:
        context_lines.append(f"ADDITIONAL USER INSTRUCTIONS:\n{instructions}")

    context_str = "\n\n".join(context_lines) if context_lines else "GENERAL REVIEW (no specific job post provided)"

    user_message = (
        f"AUDIT CONTEXT:\n{context_str}\n\n"
        f"CANDIDATE RESUME DATA:\n{json.dumps(resume_data, indent=2)}"
    )

    state = AI_GRAPH.invoke(
        {
            "provider": provider,
            "messages": [
                SystemMessage(content=CRITIC_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
            "schema": CRITIQUE_OUTPUT_SCHEMA,
            "max_tokens": 8000,
        }
    )

    result = state["result"]
    if not isinstance(result, dict) or "overall_score" not in result:
        raise ValueError("AI provider did not return a valid critique report structure.")

    # Reconcile counts accurately with returned issues list
    issues = result.get("issues", [])
    result["critical_count"] = sum(1 for i in issues if i.get("severity") == "critical")
    result["warning_count"] = sum(1 for i in issues if i.get("severity") == "warning")
    result["suggestion_count"] = sum(1 for i in issues if i.get("severity") == "suggestion")

    # Clamp overall score between 0 and 100
    score = result.get("overall_score", 70)
    result["overall_score"] = max(0, min(100, int(score)))

    return result
