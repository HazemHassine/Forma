import os
import base64
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
RESUME_TEMPLATE_IDS = {
    "modern", "classic", "minimal", "executive", "creative", "technical"
}


def generate_pdf(
    resume_data: dict,
    photo_path: str = None,
    template_id: str = "modern",
    photo_data: bytes | None = None,
    photo_content_type: str | None = None,
) -> bytes:
    """Generate a PDF from resume data using the HTML template and WeasyPrint."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("resume.html")

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

    return html.write_pdf()
