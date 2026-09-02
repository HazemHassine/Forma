import os
import base64
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
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


def render_resume_document(
    resume_data: dict,
    photo_path: str = None,
    template_id: str = "modern",
    photo_data: bytes | None = None,
    photo_content_type: str | None = None,
):
    """Render a paged résumé document before PDF serialization."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
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
    template = env.get_template(RESUME_TEMPLATE_FILES[selected_template])
    html_content = template.render(
        resume=resume_data,
        photo_uri=photo_uri,
        template_id=selected_template,
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
) -> bytes:
    """Generate a PDF from resume data using the selected document layout."""
    document = render_resume_document(
        resume_data,
        photo_path=photo_path,
        template_id=template_id,
        photo_data=photo_data,
        photo_content_type=photo_content_type,
    )
    return document.write_pdf()
