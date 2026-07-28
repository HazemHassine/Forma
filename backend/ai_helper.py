import os
import json
from typing import Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

# Resolve the backend environment file independently of the directory uvicorn
# or Docker was started from. An empty injected variable should not mask the
# configured key in this file.
BACKEND_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(
    dotenv_path=BACKEND_ENV_PATH,
    override=not bool(os.getenv("GEMINI_API_KEY")),
)

WRITING_STYLE_RULES = """
WRITING STYLE RULES - YOU MUST FOLLOW ALL OF THESE:
1. NEVER use em dashes (—). Use commas, periods, or semicolons instead.
2. NEVER use these cliche words or phrases: "eager", "excited", "passionate", "driven", "thrilled", "dedicated", "committed", "cutting-edge", "innovative", "leveraged", "spearheaded", "revolutionized", "synergy", "dynamic", "results-oriented", "self-motivated", "go-getter", "team player"
3. Write like a real human, not a LinkedIn bot or a corporate buzzword generator. Be specific and concrete.
4. Use simple, direct language. Prefer shorter sentences.
5. Do NOT start multiple bullet points with the same word.
6. Keep bullet points concise (1-2 lines each).
""".strip()

SYSTEM_PROMPTS = {
    "about_me": (
        "You are a professional resume writer. Improve this About Me section "
        "to be more impactful and tailored. Keep it concise (3-4 sentences max). "
        "If a job description is provided, tailor it to that role. "
        "Return ONLY the improved text, no explanations or formatting.\n\n"
        + WRITING_STYLE_RULES
    ),
    "work_experience": (
        "You are a professional resume writer. Improve this work experience "
        "bullet point to be more impactful, using strong action verbs and "
        "quantifiable results where possible. Keep it to 1-2 lines. "
        "If a job description is provided, emphasize relevant skills. "
        "Return ONLY the improved text, no explanations or formatting.\n\n"
        + WRITING_STYLE_RULES
    ),
    "project": (
        "You are a professional resume writer. Improve this project description "
        "bullet point to be more impactful, highlighting technical achievements "
        "and the impact of the work. Keep it to 1-2 lines. "
        "If a job description is provided, emphasize relevant skills. "
        "Return ONLY the improved text, no explanations or formatting.\n\n"
        + WRITING_STYLE_RULES
    ),
    "skills": (
        "You are a professional resume writer. Given the current skills and "
        "optionally a job description, suggest additional relevant skills or "
        "reorganize existing ones for maximum impact. Return ONLY the improved "
        "skills list, no explanations. Format as comma-separated values.\n\n"
        + WRITING_STYLE_RULES
    ),
}

OPTIMIZE_SYSTEM_PROMPT = f"""You are the senior member of a coordinated hiring team: an ATS analyst, a technical recruiter, a truthful resume editor, and a skeptical fact checker. Produce one coherent, role-specific resume rather than generic writing advice.

{WRITING_STYLE_RULES}

WORKFLOW:
1. Silently identify the role's core outcomes, required skills, terminology, seniority, and likely screening criteria.
2. Map every useful requirement to evidence that already exists in the resume.
3. Rewrite only where that mapping is supported. Prefer concrete evidence over keyword repetition.
4. Audit the result for invented claims, altered meaning, vague filler, and duplicated phrasing.

NON-NEGOTIABLE RULES:
- Preserve every fact. Never invent or infer experience, tools, metrics, responsibilities, proficiency, or outcomes.
- Never add a job-description keyword unless the source resume contains evidence for it.
- Keep the exact number and order of work, project, education, research, skill, certificate, and language entries. Identity and ordering must remain stable for safe review.
- Do not modify personal_info, education, skills, certificates, languages, references, names, employers, titles, dates, locations, project stacks, or research focus.
- You may rewrite about_me, work_experience.bullets, project descriptions/bullets, and research descriptions.
- Preserve the number of bullets in each entry. Make each bullet readable in roughly two lines and lead with varied, precise verbs.
- The about_me must be 2-3 direct sentences. It must state the candidate's relevant profile, evidence, and role direction without flattery.
- If a requested qualification has no evidence, report it as a gap. Do not hide it or manufacture a match.
- User instructions affect emphasis and tone but can never override factual accuracy.

Return ONLY valid JSON with this exact top-level structure:
{{
  "resume": <the complete resume object with the exact input schema>,
  "match_summary": <one short sentence explaining the tailoring strategy>,
  "strengths": [<up to 4 evidence-backed matches>],
  "gaps": [<up to 4 important requirements not evidenced in the resume>],
  "keywords_used": [<up to 10 job-description terms actually supported and used>]
}}
No markdown, code fences, commentary, or additional keys.
"""


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def _get_model(*, max_tokens: int) -> ChatGoogleGenerativeAI:
    """Build the LangChain Gemini integration with application defaults."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Please add it to your .env file."
        )
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=api_key,
        temperature=0.7,
        max_tokens=max_tokens,
        retries=3,
        request_timeout=180,
    )


class GeminiGraphState(TypedDict, total=False):
    messages: list
    schema: dict[str, Any]
    max_tokens: int
    result: Any


def _invoke_gemini(state: GeminiGraphState) -> GeminiGraphState:
    model = _get_model(max_tokens=state["max_tokens"])
    if state.get("schema"):
        model = model.with_structured_output(
            state["schema"],
            method="json_schema",
        )
    response = model.invoke(state["messages"])
    return {"result": response}


def _build_gemini_graph():
    builder = StateGraph(GeminiGraphState)
    builder.add_node("invoke_model", _invoke_gemini)
    builder.add_edge(START, "invoke_model")
    builder.add_edge("invoke_model", END)
    return builder.compile()


GEMINI_GRAPH = _build_gemini_graph()


def suggest_improvement(
    section_type: str,
    current_content: str,
    job_description: str = None,
    feedback: str = None,
) -> str:
    """Use Gemini to suggest improvements for a resume section."""
    system_prompt = SYSTEM_PROMPTS.get(section_type, SYSTEM_PROMPTS["about_me"])

    user_message = f"Current content:\n{current_content}"
    if job_description:
        user_message += f"\n\nJob description to tailor for:\n{job_description}"
    if feedback:
        user_message += f"\n\nSpecific user feedback/instructions to incorporate:\n{feedback}"

    state = GEMINI_GRAPH.invoke(
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ],
            "max_tokens": 500,
        }
    )
    return state["result"].text.strip()


def optimize_resume(
    resume_data: dict,
    job_description: str,
    target_role: str = None,
    company: str = None,
    instructions: str = None,
) -> dict:
    """Optimize an entire resume for a specific job description using Gemini."""
    context = {
        "target_role": target_role or "Infer from the job description",
        "company": company or "Not provided",
        "user_instructions": instructions or "No additional instructions",
    }
    user_message = (
        "TAILORING CONTEXT:\n"
        f"{json.dumps(context, indent=2)}\n\n"
        "SOURCE RESUME (the only source of candidate facts):\n"
        f"{json.dumps(resume_data, indent=2)}\n\n"
        "JOB DESCRIPTION:\n"
        f"{job_description}"
    )

    output_schema = {
        "type": "object",
        "properties": {
            "resume": {"type": "object"},
            "match_summary": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "gaps": {"type": "array", "items": {"type": "string"}},
            "keywords_used": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "resume",
            "match_summary",
            "strengths",
            "gaps",
            "keywords_used",
        ],
    }
    state = GEMINI_GRAPH.invoke(
        {
            "messages": [
                SystemMessage(content=OPTIMIZE_SYSTEM_PROMPT),
                HumanMessage(content=user_message),
            ],
            "schema": output_schema,
            "max_tokens": 8000,
        }
    )
    optimized = state["result"]

    if not isinstance(optimized, dict) or not isinstance(optimized.get("resume"), dict):
        raise ValueError("AI response did not contain the required resume object. Please try again.")

    # Guard immutable identity fields even if the model ignores an instruction.
    protected_sections = [
        "personal_info", "education", "skills", "certificates", "languages", "references"
    ]
    for section in protected_sections:
        optimized["resume"][section] = resume_data[section]

    for index, original in enumerate(resume_data.get("work_experience", [])):
        if index >= len(optimized["resume"].get("work_experience", [])):
            optimized["resume"]["work_experience"] = resume_data["work_experience"]
            break
        candidate = optimized["resume"]["work_experience"][index]
        for field in ("company", "location", "role", "dates"):
            candidate[field] = original[field]
        if len(candidate.get("bullets", [])) != len(original.get("bullets", [])):
            candidate["bullets"] = original["bullets"]

    for index, original in enumerate(resume_data.get("projects", [])):
        if index >= len(optimized["resume"].get("projects", [])):
            optimized["resume"]["projects"] = resume_data["projects"]
            break
        candidate = optimized["resume"]["projects"][index]
        for field in ("name", "type", "stack", "extra_info"):
            candidate[field] = original.get(field)
        if len(candidate.get("bullets", [])) != len(original.get("bullets", [])):
            candidate["bullets"] = original["bullets"]

    for index, original in enumerate(resume_data.get("research", [])):
        if index >= len(optimized["resume"].get("research", [])):
            optimized["resume"]["research"] = resume_data["research"]
            break
        candidate = optimized["resume"]["research"][index]
        for field in ("title", "institution", "location", "date", "focus"):
            candidate[field] = original[field]

    return optimized
