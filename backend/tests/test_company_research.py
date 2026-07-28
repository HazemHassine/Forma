import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
import openai_helper
from models import (
    CompanyResearchReportContent,
    CompanyResearchReportRequest,
)
from routers import company_research as company_research_routes

SECTION_NAMES = (
    "products_services",
    "business_model",
    "customers_markets",
    "leadership_ownership_funding",
    "financial_signals",
    "competitive_landscape",
    "recent_developments",
    "strategy_priorities",
    "culture_workplace",
    "risks_watchouts",
    "role_relevance",
)


def report_payload(
    source_url="https://example.com/about",
    *,
    researched_at="2026-07-28T12:00:00Z",
):
    report = {
        "identity": {
            "name": "Example",
            "legal_name": "Example GmbH",
            "website": "https://example.com",
            "headquarters": "Berlin, Germany",
            "founded": "2020",
            "company_type": "Private company",
            "employee_size": "51-200 employees",
            "industries": ["Software", "Artificial intelligence"],
            "source_urls": [source_url],
        },
        "executive_summary": {
            "text": "Example builds workflow software for industrial teams.",
            "source_urls": [source_url],
        },
        "follow_up_questions": [
            "How much of the announced product is generally available?",
        ],
        "sources": [
            {
                "title": "Example company overview",
                "url": source_url,
            },
        ],
        "confidence": "medium",
        "confidence_notes": "Primary company material supports the core profile.",
    }
    for section in SECTION_NAMES:
        report[section] = [
            {
                "title": section.replace("_", " ").title(),
                "detail": f"A source-backed detail for {section}.",
                "source_urls": [source_url],
            }
        ]
    if researched_at is not None:
        report["researched_at"] = researched_at
    return report


class CompanyResearchSchemaTests(unittest.TestCase):
    def test_strict_schema_contains_every_bounded_report_section(self):
        schema = openai_helper.COMPANY_RESEARCH_REPORT_SCHEMA

        self.assertFalse(schema["additionalProperties"])
        self.assertTrue(set(SECTION_NAMES).issubset(schema["required"]))
        self.assertIn("financial_signals", schema["properties"])
        self.assertIn("competitive_landscape", schema["properties"])
        self.assertIn(
            "employee_size",
            schema["properties"]["identity"]["required"],
        )
        for section in SECTION_NAMES:
            item = schema["properties"][section]["items"]
            self.assertFalse(item["additionalProperties"])
            self.assertEqual(
                item["properties"]["source_urls"]["minItems"],
                1,
            )

    def test_report_model_round_trips_all_sections(self):
        report = CompanyResearchReportContent.model_validate(report_payload())

        decoded = CompanyResearchReportContent.model_validate_json(
            report.model_dump_json()
        )

        self.assertEqual(decoded, report)
        self.assertEqual(decoded.identity.employee_size, "51-200 employees")
        self.assertEqual(len(decoded.competitive_landscape), 1)
        self.assertEqual(len(decoded.financial_signals), 1)


class CompanyResearchSanitizationTests(unittest.TestCase):
    def test_only_actually_consulted_urls_survive_across_the_report(self):
        consulted_url = "https://www.Example.com/about/?utm_source=search&a=1#team"
        canonical_model_url = "https://example.com/about?a=1"
        unconsulted_url = "https://example.com/invented"
        raw = report_payload(canonical_model_url, researched_at=None)
        raw["identity"]["source_urls"].append(unconsulted_url)
        raw["risks_watchouts"].append(
            {
                "title": "Unsupported risk",
                "detail": "This claim cites a page the search never consulted.",
                "source_urls": [unconsulted_url],
            }
        )
        raw["sources"].append({"title": "Invented", "url": unconsulted_url})

        sanitized = openai_helper.sanitize_company_research_report(
            raw,
            consulted_sources=[
                {
                    "title": "Official company overview",
                    "url": consulted_url,
                },
            ],
            company="Example",
            researched_at="2026-07-28T12:00:00Z",
            has_role_context=False,
        )

        self.assertEqual(
            sanitized["identity"]["source_urls"],
            [consulted_url],
        )
        self.assertEqual(sanitized["role_relevance"], [])
        self.assertEqual(len(sanitized["risks_watchouts"]), 1)
        self.assertEqual(sanitized["confidence"], "low")
        self.assertEqual(
            sanitized["sources"],
            [
                {
                    "title": "Official company overview",
                    "url": consulted_url,
                }
            ],
        )
        allowed_urls = {consulted_url}
        cited_urls = set(sanitized["identity"]["source_urls"])
        cited_urls.update(sanitized["executive_summary"]["source_urls"])
        for section in SECTION_NAMES:
            for item in sanitized[section]:
                cited_urls.update(item["source_urls"])
        self.assertEqual(cited_urls, allowed_urls)

    def test_unsourced_identity_and_summary_are_reset_not_laundered(self):
        raw = report_payload(
            "https://unconsulted.example/fact",
            researched_at=None,
        )

        sanitized = openai_helper.sanitize_company_research_report(
            raw,
            consulted_sources=[],
            company="User supplied company",
            researched_at="2026-07-28T12:00:00Z",
            has_role_context=True,
        )

        self.assertEqual(sanitized["identity"]["name"], "User supplied company")
        self.assertEqual(sanitized["identity"]["legal_name"], "")
        self.assertEqual(sanitized["identity"]["employee_size"], "")
        self.assertEqual(sanitized["identity"]["industries"], [])
        self.assertEqual(
            sanitized["executive_summary"]["text"],
            "Research was limited; no source-backed company facts were verified.",
        )
        self.assertEqual(sanitized["follow_up_questions"], [])
        self.assertEqual(sanitized["sources"], [])
        for section in SECTION_NAMES:
            self.assertEqual(sanitized[section], [])

    def test_sources_from_discarded_items_do_not_leak_into_report(self):
        primary_url = "https://example.com/about"
        discarded_url = "https://example.com/discarded"
        raw = report_payload(primary_url, researched_at=None)
        raw["financial_signals"].append(
            {
                "title": "",
                "detail": "This item is invalid because it has no title.",
                "source_urls": [discarded_url],
            }
        )
        raw["executive_summary"] = {
            "text": "",
            "source_urls": [discarded_url],
        }

        sanitized = openai_helper.sanitize_company_research_report(
            raw,
            consulted_sources=[
                {"title": "Company overview", "url": primary_url},
                {"title": "Discarded source", "url": discarded_url},
            ],
            company="Example",
            researched_at="2026-07-28T12:00:00Z",
            has_role_context=True,
        )

        self.assertEqual(
            [source["url"] for source in sanitized["sources"]],
            [primary_url],
        )
        self.assertEqual(
            sanitized["executive_summary"]["source_urls"],
            [primary_url],
        )
        self.assertNotIn(discarded_url, sanitized["confidence_notes"])


class CompanyResearchHelperTests(unittest.TestCase):
    def test_helper_requires_web_search_and_uses_dedicated_model(self):
        consulted_url = "https://example.com/about"
        raw = report_payload(consulted_url, researched_at=None)
        response_payload = {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "title": "Official company overview",
                                "url": consulted_url,
                            },
                        ],
                    },
                }
            ]
        }

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(raw), response_payload),
        ) as structured_response:
            result = openai_helper.research_company_report(
                company="Example",
                website_url="https://example.com",
                role="AI Engineer",
                job_context="Build reliable AI systems.",
                focus="Engineering culture and product direction",
            )

        call = structured_response.call_args.kwargs
        self.assertEqual(call["schema_name"], "company_research_report")
        self.assertEqual(call["tools"], [{"type": "web_search"}])
        self.assertEqual(call["tool_choice"], "required")
        self.assertEqual(
            call["include"],
            ["web_search_call.action.sources"],
        )
        self.assertEqual(
            call["model"],
            openai_helper.OPENAI_COMPANY_RESEARCH_MODEL,
        )
        self.assertIs(call["background"], True)
        self.assertEqual(
            call["background_timeout"],
            openai_helper.OPENAI_COMPANY_RESEARCH_MAX_WAIT,
        )
        self.assertEqual(
            call["context"]["focus"],
            "Engineering culture and product direction",
        )
        self.assertEqual(len(result["role_relevance"]), 1)
        self.assertTrue(result["researched_at"].endswith("Z"))


class CompanyResearchBackgroundTests(unittest.TestCase):
    def test_background_retrieval_uses_the_response_get_endpoint(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "id": "resp_123",
                "status": "completed",
                "output_text": "{}",
            }
        ).encode("utf-8")

        with (
            mock.patch.dict(
                openai_helper.os.environ,
                {"OPENAI_API_KEY": "test-key"},
            ),
            mock.patch.object(
                openai_helper.request,
                "urlopen",
                return_value=response,
            ) as urlopen,
        ):
            result = openai_helper._retrieve_response("resp_123")

        sent_request = urlopen.call_args.args[0]
        self.assertEqual(sent_request.get_method(), "GET")
        self.assertEqual(
            sent_request.full_url,
            "https://api.openai.com/v1/responses/resp_123",
        )
        self.assertEqual(result["status"], "completed")

    def test_structured_response_runs_through_langgraph(self):
        raw = openai_helper.AIMessage(content="")
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
            "required": [],
        }

        with mock.patch.object(
            openai_helper.STRUCTURED_OUTPUT_GRAPH,
            "invoke",
            return_value={"result": {}, "raw": raw},
        ) as graph_invoke:
            result, payload = openai_helper._structured_response(
                instructions="Return an empty object.",
                context={},
                schema_name="background_test",
                schema=schema,
                background=True,
                background_timeout=30,
            )

        self.assertEqual(result, {})
        self.assertIs(payload, raw)
        graph_state = graph_invoke.call_args.args[0]
        self.assertEqual(graph_state["schema"]["title"], "background_test")
        self.assertEqual(
            graph_state["instructions"],
            "Return an empty object.",
        )

    def test_background_polling_waits_until_completed(self):
        initial = {"id": "resp_123", "status": "queued"}
        in_progress = {"id": "resp_123", "status": "in_progress"}
        completed = {
            "id": "resp_123",
            "status": "completed",
            "output_text": "{}",
        }

        with (
            mock.patch.object(
                openai_helper,
                "_retrieve_response",
                side_effect=[in_progress, completed],
            ) as retrieve,
            mock.patch.object(
                openai_helper.time,
                "monotonic",
                side_effect=[0, 0, 1],
            ),
            mock.patch.object(openai_helper.time, "sleep") as sleep,
        ):
            result = openai_helper._poll_background_response(
                initial,
                timeout=30,
                poll_interval=0.1,
            )

        self.assertEqual(result, completed)
        self.assertEqual(retrieve.call_count, 2)
        retrieve.assert_called_with("resp_123")
        self.assertEqual(sleep.call_count, 2)

    def test_background_polling_reports_a_bounded_timeout(self):
        initial = {"id": "resp_slow", "status": "queued"}

        with (
            mock.patch.object(
                openai_helper.time,
                "monotonic",
                side_effect=[0, 31],
            ),
            mock.patch.object(
                openai_helper,
                "_retrieve_response",
            ) as retrieve,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "taking longer than expected",
            ):
                openai_helper._poll_background_response(
                    initial,
                    timeout=30,
                    poll_interval=0,
                )

        retrieve.assert_not_called()

    def test_background_terminal_failure_surfaces_provider_detail(self):
        failed = {
            "id": "resp_failed",
            "status": "failed",
            "error": {"message": "Search execution failed."},
        }

        with self.assertRaisesRegex(
            ValueError,
            "Search execution failed",
        ):
            openai_helper._poll_background_response(
                failed,
                timeout=30,
                poll_interval=0,
            )


class CompanyResearchPersistenceTests(unittest.TestCase):
    def test_database_migration_is_idempotent_and_preserves_existing_data(self):
        with tempfile.TemporaryDirectory(prefix="company-research-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                connection = sqlite3.connect(db_path)
                connection.execute(
                    """
                    INSERT INTO resume_versions (name, data, is_current)
                    VALUES (?, ?, ?)
                    """,
                    ("Existing resume", "{}", 1),
                )
                connection.commit()
                connection.close()

                database.init_db()
                connection = sqlite3.connect(db_path)
                resume_count = connection.execute(
                    "SELECT COUNT(*) FROM resume_versions"
                ).fetchone()[0]
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(company_research_reports)"
                    ).fetchall()
                }
                indexes = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA index_list(company_research_reports)"
                    ).fetchall()
                }
                connection.close()

        self.assertEqual(resume_count, 1)
        self.assertTrue(
            {
                "company",
                "website_url",
                "role",
                "job_context",
                "focus",
                "report",
                "researched_at",
            }.issubset(columns)
        )
        self.assertIn("idx_company_research_created", indexes)

    def test_router_create_list_get_and_delete_persist_sanitized_snapshot(self):
        generated = report_payload()

        with tempfile.TemporaryDirectory(prefix="company-research-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                request_model = CompanyResearchReportRequest(
                    company="  Example  ",
                    website_url=" https://example.com ",
                    role=" AI Engineer ",
                    job_context=" Build reliable systems. ",
                    focus=" Product and culture ",
                )
                with mock.patch.object(
                    company_research_routes,
                    "research_company_report",
                    return_value=copy.deepcopy(generated),
                ) as research:
                    created = company_research_routes.create_company_research_report(
                        request_model
                    )

                listed = company_research_routes.list_company_research_reports()
                filtered = company_research_routes.list_company_research_reports(
                    company="example",
                )
                fetched = company_research_routes.get_company_research_report(
                    created.id
                )
                deleted = company_research_routes.delete_company_research_report(
                    created.id
                )
                with self.assertRaises(HTTPException) as missing:
                    company_research_routes.get_company_research_report(created.id)

        self.assertEqual(research.call_args.kwargs["company"], "Example")
        self.assertEqual(
            research.call_args.kwargs["focus"],
            "Product and culture",
        )
        self.assertEqual(created.focus, "Product and culture")
        self.assertEqual(created.report, fetched.report)
        self.assertEqual(len(listed), 1)
        self.assertEqual(filtered, listed)
        self.assertEqual(listed[0].legal_name, "Example GmbH")
        self.assertEqual(
            deleted,
            {"message": "Company research report deleted"},
        )
        self.assertEqual(missing.exception.status_code, 404)

    def test_upstream_failure_does_not_create_a_report(self):
        with tempfile.TemporaryDirectory(prefix="company-research-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                with mock.patch.object(
                    company_research_routes,
                    "research_company_report",
                    side_effect=ValueError("Research unavailable"),
                ):
                    with self.assertRaises(HTTPException) as failure:
                        company_research_routes.create_company_research_report(
                            CompanyResearchReportRequest(company="Example")
                        )
                connection = sqlite3.connect(db_path)
                count = connection.execute(
                    "SELECT COUNT(*) FROM company_research_reports"
                ).fetchone()[0]
                connection.close()

        self.assertEqual(failure.exception.status_code, 400)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
