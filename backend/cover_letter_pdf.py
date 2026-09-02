import hashlib
import json
import os
import threading
from collections import OrderedDict

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
JINJA_ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

_COVER_LETTER_PDF_CACHE_LOCK = threading.Lock()
_COVER_LETTER_PDF_CACHE: OrderedDict[str, bytes] = OrderedDict()
_COVER_LETTER_PAGE_COUNT_CACHE: OrderedDict[str, int] = OrderedDict()
_COVER_LETTER_CACHE_MAX_SIZE = 64


def _compute_cover_letter_cache_key(content: dict, resume_data: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(json.dumps(content, sort_keys=True).encode("utf-8"))
    hasher.update(json.dumps(resume_data, sort_keys=True).encode("utf-8"))
    signature_path = STATIC_DIR / "documents" / "signature.png"
    if signature_path.is_file():
        stat = signature_path.stat()
        hasher.update(f"{stat.st_mtime}:{stat.st_size}".encode("utf-8"))
    return hasher.hexdigest()


def clear_cover_letter_cache() -> None:
    """Clear the in-memory cover letter PDF and page count cache."""
    with _COVER_LETTER_PDF_CACHE_LOCK:
        _COVER_LETTER_PDF_CACHE.clear()
        _COVER_LETTER_PAGE_COUNT_CACHE.clear()


def _render_cover_letter(content: dict, resume_data: dict):
    template = JINJA_ENV.get_template("cover_letter.html")
    personal = resume_data["personal_info"]
    education = resume_data.get("education", [])
    if education:
        subtitle = f"{education[0]['degree']} | {education[0]['institution']}"
    else:
        subtitle = personal.get("title", "")

    signature_path = STATIC_DIR / "documents" / "signature.png"
    signature_uri = (
        f"file://{signature_path.resolve()}"
        if signature_path.is_file()
        else None
    )

    html_content = template.render(
        letter=content,
        personal=personal,
        subtitle=subtitle,
        signature_uri=signature_uri,
    )
    return HTML(string=html_content, base_url=BASE_DIR).render()


def cover_letter_page_count(content: dict, resume_data: dict, use_cache: bool = True) -> int:
    if use_cache:
        key = _compute_cover_letter_cache_key(content, resume_data)
        with _COVER_LETTER_PDF_CACHE_LOCK:
            if key in _COVER_LETTER_PAGE_COUNT_CACHE:
                _COVER_LETTER_PAGE_COUNT_CACHE.move_to_end(key)
                return _COVER_LETTER_PAGE_COUNT_CACHE[key]

    doc = _render_cover_letter(content, resume_data)
    count = len(doc.pages)

    if use_cache:
        pdf_bytes = doc.write_pdf()
        with _COVER_LETTER_PDF_CACHE_LOCK:
            _COVER_LETTER_PAGE_COUNT_CACHE[key] = count
            _COVER_LETTER_PDF_CACHE[key] = pdf_bytes
            if len(_COVER_LETTER_PAGE_COUNT_CACHE) > _COVER_LETTER_CACHE_MAX_SIZE:
                _COVER_LETTER_PAGE_COUNT_CACHE.popitem(last=False)
            if len(_COVER_LETTER_PDF_CACHE) > _COVER_LETTER_CACHE_MAX_SIZE:
                _COVER_LETTER_PDF_CACHE.popitem(last=False)

    return count


def generate_cover_letter_pdf(content: dict, resume_data: dict, use_cache: bool = True) -> bytes:
    if use_cache:
        key = _compute_cover_letter_cache_key(content, resume_data)
        with _COVER_LETTER_PDF_CACHE_LOCK:
            if key in _COVER_LETTER_PDF_CACHE:
                _COVER_LETTER_PDF_CACHE.move_to_end(key)
                return _COVER_LETTER_PDF_CACHE[key]

    doc = _render_cover_letter(content, resume_data)
    pdf_bytes = doc.write_pdf()

    if use_cache:
        with _COVER_LETTER_PDF_CACHE_LOCK:
            _COVER_LETTER_PDF_CACHE[key] = pdf_bytes
            _COVER_LETTER_PAGE_COUNT_CACHE[key] = len(doc.pages)
            if len(_COVER_LETTER_PDF_CACHE) > _COVER_LETTER_CACHE_MAX_SIZE:
                _COVER_LETTER_PDF_CACHE.popitem(last=False)
            if len(_COVER_LETTER_PAGE_COUNT_CACHE) > _COVER_LETTER_CACHE_MAX_SIZE:
                _COVER_LETTER_PAGE_COUNT_CACHE.popitem(last=False)

    return pdf_bytes
