import copy
import os
import json
from typing import Any, TypedDict

from dotenv import dotenv_values, load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

# Resolve the backend environment file independently of the directory uvicorn
# or Docker was started from. An empty injected variable should not mask the
# configured key in this file.
BACKEND_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=BACKEND_ENV_PATH, override=False)
_file_environment = dotenv_values(BACKEND_ENV_PATH)
for _api_key_name in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
    if not os.getenv(_api_key_name) and _file_environment.get(_api_key_name):
        os.environ[_api_key_name] = _file_environment[_api_key_name]

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
  "resume": {{
    "about_me": <tailored 2-3 sentence profile>,
    "work_experience": [{{"bullets": [<concise tailored bullet points matching original count>]}}],
    "projects": [{{"description": <tailored impact description>, "bullets": [<tailored bullets matching original count>]}}],
    "research": [{{"description": <tailored research description>}}]
  }},
  "match_summary": <one short sentence explaining the tailoring strategy>,
  "strengths": [<up to 4 evidence-backed matches>],
  "gaps": [<up to 4 important requirements not evidenced in the resume>],
  "keywords_used": [<up to 10 job-description terms actually supported and used>]
}}
No markdown, code fences, commentary, or additional keys.
"""


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OPENAI_RESUME_MODEL = os.getenv("OPENAI_RESUME_MODEL", "gpt-5.6-sol")


def _get_model(*, provider: str, max_tokens: int):
    """Build the selected chat model with shared application defaults."""
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Add it to backend/.env and restart the backend."
            )
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=api_key,
            thinking_level="medium",
            max_tokens=max_tokens,
            retries=3,
            request_timeout=180,
        )

    if provider == "chatgpt":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Add it to backend/.env and restart the backend."
            )
        return ChatOpenAI(
            model=OPENAI_RESUME_MODEL,
            api_key=api_key,
            use_responses_api=True,
            store=False,
            reasoning_effort="medium",
            verbosity="medium",
            timeout=180,
            max_retries=3,
            max_tokens=max_tokens,
        )

    raise ValueError(
        f"Unsupported AI provider '{provider}'. Choose 'gemini' or 'chatgpt'."
    )


class AIGraphState(TypedDict, total=False):
    provider: str
    messages: list
    schema: dict[str, Any]
    max_tokens: int
    result: Any


def _clean_schema_for_gemini(schema: Any) -> Any:
    """Strip constraints unsupported by Gemini's JSON schema parser."""
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for key, value in schema.items():
        if key in {"minItems", "maxItems"}:
            continue
        if isinstance(value, dict):
            cleaned[key] = _clean_schema_for_gemini(value)
        elif isinstance(value, list):
            cleaned[key] = [_clean_schema_for_gemini(item) for item in value]
        else:
            cleaned[key] = value
    return cleaned


def _invoke_model(state: AIGraphState) -> AIGraphState:
    provider = state.get("provider", "gemini")
    model = _get_model(
        provider=provider,
        max_tokens=state["max_tokens"],
    )
    if state.get("schema"):
        schema = (
            _clean_schema_for_gemini(state["schema"])
            if provider == "gemini"
            else state["schema"]
        )
        model = model.with_structured_output(
            schema,
            method="json_schema",
        )
    response = model.invoke(state["messages"])
    return {"result": response}


def _build_ai_graph():
    builder = StateGraph(AIGraphState)
    builder.add_node("invoke_model", _invoke_model)
    builder.add_edge(START, "invoke_model")
    builder.add_edge("invoke_model", END)
    return builder.compile()


AI_GRAPH = _build_ai_graph()
# Kept as an alias for callers that imported the previous graph name.
GEMINI_GRAPH = AI_GRAPH


def _result_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content.strip()
    raise ValueError("The selected AI provider returned no text.")


def suggest_improvement(
    section_type: str,
    current_content: str,
    job_description: str = None,
    feedback: str = None,
    provider: str = "gemini",
) -> str:
    """Use the selected provider to improve a resume section."""
    system_prompt = SYSTEM_PROMPTS.get(section_type, SYSTEM_PROMPTS["about_me"])

    user_message = f"Current content:\n{current_content}"
    if job_description:
        user_message += f"\n\nJob description to tailor for:\n{job_description}"
    if feedback:
        user_message += f"\n\nSpecific user feedback/instructions to incorporate:\n{feedback}"

    state = AI_GRAPH.invoke(
        {
            "provider": provider,
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ],
            "max_tokens": 500,
        }
    )
    return _result_text(state["result"])


def optimize_resume(
    resume_data: dict,
    job_description: str,
    target_role: str = None,
    company: str = None,
    instructions: str = None,
    provider: str = "gemini",
) -> dict:
    """Optimize a resume with the selected AI provider."""
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
            "resume": {
                "type": "object",
                "properties": {
                    "about_me": {"type": "string"},
                    "work_experience": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "company": {"type": "string"},
                                "role": {"type": "string"},
                                "bullets": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["bullets"],
                        },
                    },
                    "projects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "bullets": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["description", "bullets"],
                        },
                    },
                    "research": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["description"],
                        },
                    },
                },
                "required": ["about_me"],
            },
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
    state = AI_GRAPH.invoke(
        {
            "provider": provider,
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

    # Start with a deep copy of the source resume data so all fields, structure,
    # and unedited sections remain completely intact and valid.
    final_resume = copy.deepcopy(resume_data)
    model_resume = optimized.get("resume") or {}

    # 1. Tailor about_me if provided by the model
    if model_resume.get("about_me"):
        final_resume["about_me"] = str(model_resume["about_me"]).strip()

    # 2. Update work_experience bullets while strictly preserving company, location, role, dates
    original_work = resume_data.get("work_experience", [])
    model_work = model_resume.get("work_experience", [])
    if isinstance(model_work, list):
        for index, original in enumerate(original_work):
            if index < len(model_work) and isinstance(model_work[index], dict):
                candidate = model_work[index]
                bullets = candidate.get("bullets")
                if isinstance(bullets, list) and len(bullets) == len(original.get("bullets", [])):
                    final_resume["work_experience"][index]["bullets"] = [str(b).strip() for b in bullets]

    # 3. Update projects description and bullets while preserving name, type, stack, extra_info
    original_projects = resume_data.get("projects", [])
    model_projects = model_resume.get("projects", [])
    if isinstance(model_projects, list):
        for index, original in enumerate(original_projects):
            if index < len(model_projects) and isinstance(model_projects[index], dict):
                candidate = model_projects[index]
                if candidate.get("description"):
                    final_resume["projects"][index]["description"] = str(candidate["description"]).strip()
                bullets = candidate.get("bullets")
                if isinstance(bullets, list) and len(bullets) == len(original.get("bullets", [])):
                    final_resume["projects"][index]["bullets"] = [str(b).strip() for b in bullets]

    # 4. Update research description while preserving title, institution, location, date, focus
    original_research = resume_data.get("research", [])
    model_research = model_resume.get("research", [])
    if isinstance(model_research, list):
        for index, original in enumerate(original_research):
            if index < len(model_research) and isinstance(model_research[index], dict):
                candidate = model_research[index]
                if candidate.get("description"):
                    final_resume["research"][index]["description"] = str(candidate["description"]).strip()

    optimized["resume"] = final_resume
    return optimized
