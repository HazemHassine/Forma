import os

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


def _render_cover_letter(content: dict, resume_data: dict):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    template = env.get_template("cover_letter.html")
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


def cover_letter_page_count(content: dict, resume_data: dict) -> int:
    return len(_render_cover_letter(content, resume_data).pages)


def generate_cover_letter_pdf(content: dict, resume_data: dict) -> bytes:
    return _render_cover_letter(content, resume_data).write_pdf()
