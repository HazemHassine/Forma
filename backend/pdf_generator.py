import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from config import STATIC_DIR


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


def generate_pdf(resume_data: dict, photo_path: str = None) -> bytes:
    """Generate a PDF from resume data using the HTML template and WeasyPrint."""
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("resume.html")

    if photo_path is None:
        photo_path = STATIC_DIR / "profile.jpg"

    photo_uri = (
        f"file://{os.path.abspath(photo_path)}"
        if os.path.isfile(photo_path)
        else None
    )

    html_content = template.render(
        resume=resume_data,
        photo_uri=photo_uri,
    )

    # Use base_url so relative resources resolve correctly
    html = HTML(
        string=html_content,
        base_url=os.path.dirname(__file__)
    )

    return html.write_pdf()
