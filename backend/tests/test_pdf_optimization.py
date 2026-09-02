import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from cover_letter_pdf import (
    clear_cover_letter_cache,
    cover_letter_page_count,
    generate_cover_letter_pdf,
    _COVER_LETTER_PDF_CACHE,
    _COVER_LETTER_PAGE_COUNT_CACHE,
)
from pdf_generator import (
    clear_pdf_cache,
    generate_pdf,
    _PDF_CACHE,
    JINJA_ENV,
)
from routers import resumes


SAMPLE_RESUME = {
    "personal_info": {
        "name": "Jane Doe",
        "title": "Senior Staff Engineer",
        "email": "jane@example.com",
        "phone": "+1 555-0199",
        "address": "San Francisco, CA",
        "github": "github.com/janedoe",
        "linkedin": "linkedin.com/in/janedoe",
    },
    "about_me": "Experienced system engineer focusing on performance and reliability.",
    "education": [
        {
            "institution": "Tech University",
            "degree": "B.S. Computer Science",
            "dates": "2016-2020",
            "location": "Boston, MA",
        }
    ],
    "work_experience": [
        {
            "company": "FastCloud Inc.",
            "role": "Lead Infrastructure Engineer",
            "dates": "2020-Present",
            "location": "Remote",
            "bullets": ["Reduced p99 latency by 45%."],
        }
    ],
    "projects": [],
    "research": [],
    "skills": [{"category": "Languages", "items": ["Python", "C++", "Go"]}],
    "certificates": [],
    "languages": [{"language": "English", "level": "Native"}],
    "references": "Available upon request.",
}

SAMPLE_LETTER = {
    "recipient": "Engineering Team\nFastCloud Inc.",
    "body": "I am writing to express my enthusiasm for the Senior Staff Engineer role at FastCloud.",
}


class PdfOptimizationTests(unittest.TestCase):
    def setUp(self):
        clear_pdf_cache()
        clear_cover_letter_cache()

    def tearDown(self):
        clear_pdf_cache()
        clear_cover_letter_cache()

    def test_jinja_environment_is_singleton(self):
        """Jinja environment should be initialized at module level."""
        self.assertIsNotNone(JINJA_ENV)
        template1 = JINJA_ENV.get_template("resume.html")
        template2 = JINJA_ENV.get_template("resume.html")
        self.assertIs(template1, template2)

    def test_resume_pdf_caching_hit_and_miss(self):
        """Second generate_pdf call with identical parameters should hit in-memory cache."""
        self.assertEqual(len(_PDF_CACHE), 0)

        # First call: miss
        t0 = time.time()
        pdf1 = generate_pdf(SAMPLE_RESUME, template_id="modern")
        t_miss = time.time() - t0
        self.assertGreater(len(pdf1), 1000)
        self.assertEqual(len(_PDF_CACHE), 1)

        # Second call: hit (should be orders of magnitude faster)
        t0 = time.time()
        pdf2 = generate_pdf(SAMPLE_RESUME, template_id="modern")
        t_hit = time.time() - t0

        self.assertEqual(pdf1, pdf2)
        self.assertLess(t_hit, t_miss / 10)

    def test_resume_pdf_cache_invalidation_on_data_change(self):
        """Altering resume data or template ID must produce distinct cache entries."""
        pdf1 = generate_pdf(SAMPLE_RESUME, template_id="modern")
        self.assertEqual(len(_PDF_CACHE), 1)

        # Different template
        pdf_ats = generate_pdf(SAMPLE_RESUME, template_id="ats")
        self.assertEqual(len(_PDF_CACHE), 2)
        self.assertNotEqual(pdf1, pdf_ats)

        # Modified resume data
        modified_resume = dict(SAMPLE_RESUME, about_me="Updated text about me.")
        pdf_mod = generate_pdf(modified_resume, template_id="modern")
        self.assertEqual(len(_PDF_CACHE), 3)
        self.assertNotEqual(pdf1, pdf_mod)

    def test_cover_letter_local_fonts_and_caching(self):
        """Cover letters should use local fonts and cache page count + PDF bytes."""
        # Ensure local font files exist on disk
        font_dir = BACKEND_DIR / "static" / "fonts"
        self.assertTrue((font_dir / "LeagueSpartan-Regular.ttf").is_file())
        self.assertTrue((font_dir / "LeagueSpartan-Bold.ttf").is_file())
        self.assertTrue((font_dir / "Rubik-Regular.ttf").is_file())

        self.assertEqual(len(_COVER_LETTER_PAGE_COUNT_CACHE), 0)
        self.assertEqual(len(_COVER_LETTER_PDF_CACHE), 0)

        # Page count computation renders and caches both page count and PDF
        t0 = time.time()
        pages = cover_letter_page_count(SAMPLE_LETTER, SAMPLE_RESUME)
        t_first = time.time() - t0
        self.assertEqual(pages, 1)
        self.assertEqual(len(_COVER_LETTER_PAGE_COUNT_CACHE), 1)
        self.assertEqual(len(_COVER_LETTER_PDF_CACHE), 1)

        # Subsequent generate_cover_letter_pdf should be an instant cache hit
        t0 = time.time()
        pdf_bytes = generate_cover_letter_pdf(SAMPLE_LETTER, SAMPLE_RESUME)
        t_hit = time.time() - t0
        self.assertGreater(len(pdf_bytes), 500)
        self.assertLess(t_hit, 0.05)  # Cache hit is sub-millisecond to ~few ms

    def test_resume_routes_are_sync_functions(self):
        """Download and preview routes must not be coroutine functions so they run in threadpools."""
        import inspect
        self.assertFalse(inspect.iscoroutinefunction(resumes.download_resume_pdf))
        self.assertFalse(inspect.iscoroutinefunction(resumes.preview_resume_pdf))


if __name__ == "__main__":
    unittest.main()
