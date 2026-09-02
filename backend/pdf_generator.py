import os
import base64
import hashlib
import json
import threading
from collections import OrderedDict
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
JINJA_ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

RESUME_TEMPLATE_FILES = {
    "modern": "resume.html",
    "classic": "resume.html",
    "minimal": "resume.html",
    "executive": "resume.html",
    "creative": "resume.html",
    "technical": "resume.html",
    "latex": "resume_latex.html",
    "ats": "resume_ats.html",
    "timeline": "resume_timeline.html",
}
RESUME_TEMPLATE_IDS = set(RESUME_TEMPLATE_FILES)
DEFAULT_SECTION_ORDER = [
    "about_me",
    "work_experience",
    "education",
    "projects",
    "research",
    "skills",
    "certificates",
    "languages",
    "references",
]

_PDF_CACHE_LOCK = threading.Lock()
_PDF_CACHE: OrderedDict[str, bytes] = OrderedDict()
_PDF_CACHE_MAX_SIZE = 64


def _compute_cache_key(
    resume_data: dict,
    template_id: str,
    photo_path: str | None,
    photo_data: bytes | None,
    photo_content_type: str | None,
) -> str:
    hasher = hashlib.sha256()
    hasher.update(template_id.encode("utf-8"))
    hasher.update(json.dumps(resume_data, sort_keys=True).encode("utf-8"))
    if photo_data:
        hasher.update(photo_data)
        if photo_content_type:
            hasher.update(photo_content_type.encode("utf-8"))
    elif photo_path and os.path.isfile(photo_path):
        stat = os.stat(photo_path)
        hasher.update(f"{photo_path}:{stat.st_mtime}:{stat.st_size}".encode("utf-8"))
    return hasher.hexdigest()


def clear_pdf_cache() -> None:
    """Clear the in-memory PDF cache."""
    with _PDF_CACHE_LOCK:
        _PDF_CACHE.clear()


def render_resume_document(
    resume_data: dict,
    photo_path: str = None,
    template_id: str = "modern",
    photo_data: bytes | None = None,
    photo_content_type: str | None = None,
):
    """Render a paged résumé document before PDF serialization."""
    if photo_path is None:
        photo_path = STATIC_DIR / "profile.jpg"

    if photo_data:
        encoded = base64.b64encode(photo_data).decode("ascii")
        photo_uri = f"data:{photo_content_type or 'image/jpeg'};base64,{encoded}"
    else:
        photo_uri = (
            f"file://{os.path.abspath(photo_path)}"
            if os.path.isfile(photo_path)
            else None
        )

    selected_template = (
        template_id if template_id in RESUME_TEMPLATE_IDS else "modern"
    )
    template = JINJA_ENV.get_template(RESUME_TEMPLATE_FILES[selected_template])

    raw_order = resume_data.get("section_order")
    if isinstance(raw_order, list):
        section_order = [s for s in raw_order if s in DEFAULT_SECTION_ORDER]
    else:
        section_order = list(DEFAULT_SECTION_ORDER)

    html_content = template.render(
        resume=resume_data,
        photo_uri=photo_uri,
        template_id=selected_template,
        section_order=section_order,
    )

    # Use base_url so relative resources resolve correctly
    html = HTML(
        string=html_content,
        base_url=os.path.dirname(__file__)
    )

    return html.render()


def generate_pdf(
    resume_data: dict,
    photo_path: str = None,
    template_id: str = "modern",
    photo_data: bytes | None = None,
    photo_content_type: str | None = None,
    use_cache: bool = True,
) -> bytes:
    """Generate a PDF from resume data using the selected document layout."""
    if use_cache:
        key = _compute_cache_key(
            resume_data,
            template_id,
            photo_path,
            photo_data,
            photo_content_type,
        )
        with _PDF_CACHE_LOCK:
            if key in _PDF_CACHE:
                _PDF_CACHE.move_to_end(key)
                return _PDF_CACHE[key]

    document = render_resume_document(
        resume_data,
        photo_path=photo_path,
        template_id=template_id,
        photo_data=photo_data,
        photo_content_type=photo_content_type,
    )
    pdf_bytes = document.write_pdf()

    if use_cache:
        with _PDF_CACHE_LOCK:
            _PDF_CACHE[key] = pdf_bytes
            if len(_PDF_CACHE) > _PDF_CACHE_MAX_SIZE:
                _PDF_CACHE.popitem(last=False)

    return pdf_bytes
