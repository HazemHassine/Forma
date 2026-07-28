import copy
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error as urllib_error


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
import openai_helper
from models import (
    CoverLetter,
    CoverLetterAnalysis,
    CoverLetterAnalyzeRequest,
    CoverLetterGenerateRequest,
    CoverLetterGenerationContext,
)
from routers import cover_letters as cover_letter_routes


def analysis_payload():
    return {
        "company": "Example GmbH",
        "position": "AI Engineer",
        "role_summary": "Build reliable AI-assisted products with a product team.",
        "key_requirements": [
            {"requirement": "Python", "importance": "high"},
        ],
        "evidence_matches": [
            {
                "requirement": "Python",
                "resume_evidence": "Built Python analytical pipelines.",
                "relevance": "Direct implementation experience.",
            },
        ],
        "gaps": ["No production on-call experience is listed."],
        "strategy": "Lead with the directly relevant implementation work.",
        "questions": [
            {
                "id": "company_motivation",
                "question": "Why does this company's work interest you?",
                "why": "A personal reason would make the opening more specific.",
                "placeholder": "A short, honest reason.",
            },
        ],
        "observations": [
            {
                "title": "Strong implementation overlap",
                "detail": "The role prioritizes Python delivery, and the resume shows Python pipeline work.",
                "impact": "Use the pipeline example as the main proof point.",
            },
            {
                "title": "Operational evidence is missing",
                "detail": "The post mentions on-call work, but the resume does not.",
                "impact": "Do not imply production support experience.",
            },
        ],
        "angles": [
            {
                "id": "reliable_builder",
                "title": "Reliable product builder",
                "approach": "Center the letter on turning Python work into dependable product outcomes.",
                "supporting_evidence": [
                    "Built Python analytical pipelines.",
                ],
                "caution": "Do not claim production on-call ownership.",
            },
            {
                "id": "product_collaborator",
                "title": "Technical product collaborator",
                "approach": "Emphasize collaboration around implementation decisions.",
                "supporting_evidence": [
                    "Worked on analytical pipelines.",
                ],
                "caution": "The resume does not name specific product stakeholders.",
            },
        ],
        "recommended_angle_id": "reliable_builder",
        "paragraph_plan": [
            {
                "paragraph": 1,
                "purpose": "Connect the current situation to the role.",
                "evidence": "Candidate summary and verified role title.",
            },
            {
                "paragraph": 2,
                "purpose": "Show the strongest implementation match.",
                "evidence": "Built Python analytical pipelines.",
            },
            {
                "paragraph": 3,
                "purpose": "Add a second proof point and handle the learning edge.",
                "evidence": "Other resume evidence; no on-call claim.",
            },
            {
                "paragraph": 4,
                "purpose": "State a practical contribution and close.",
                "evidence": "Verified overlap only.",
            },
        ],
        "excluded_claims": [
            {
                "claim": "Has production on-call experience.",
                "reason": "No such experience appears in the resume.",
            },
        ],
    }


def paragraph(word_count):
    return " ".join(["evidence"] * word_count)


def valid_letter(word_counts=(55, 55, 55, 55)):
    return {
        "company": "Example GmbH",
        "position": "AI Engineer",
        "recipient": "Hiring Team",
        "subject": "Application for AI Engineer",
        "paragraphs": [paragraph(count) for count in word_counts],
        "sign_off": "Best regards,",
    }


def content_payload():
    return {
        "company": "Example GmbH",
        "position": "AI Engineer",
        "recipient": "Hiring Team",
        "subject": "Application for AI Engineer",
        "date": "Jul 28th 2026",
        "paragraphs": ["One.", "Two.", "Three.", "Four."],
        "sign_off": "Best regards,",
    }


class CoverLetterAnalysisTests(unittest.TestCase):
    def test_legacy_analysis_payload_gets_empty_inspectable_defaults(self):
        legacy_payload = analysis_payload()
        for field in (
            "observations",
            "angles",
            "recommended_angle_id",
            "paragraph_plan",
            "excluded_claims",
        ):
            legacy_payload.pop(field)

        analysis = CoverLetterAnalysis.model_validate(legacy_payload)

        self.assertEqual(analysis.observations, [])
        self.assertEqual(analysis.angles, [])
        self.assertEqual(analysis.recommended_angle_id, "")
        self.assertEqual(analysis.paragraph_plan, [])
        self.assertEqual(analysis.excluded_claims, [])

    def test_analysis_schema_requires_all_inspectable_outputs(self):
        new_fields = {
            "observations",
            "angles",
            "recommended_angle_id",
            "paragraph_plan",
            "excluded_claims",
        }

        self.assertTrue(new_fields.issubset(openai_helper.ANALYSIS_SCHEMA["required"]))
        self.assertEqual(
            openai_helper.ANALYSIS_SCHEMA["properties"]["angles"]["minItems"],
            2,
        )
        self.assertEqual(
            openai_helper.ANALYSIS_SCHEMA["properties"]["angles"]["maxItems"],
            3,
        )
        self.assertEqual(
            openai_helper.ANALYSIS_SCHEMA["properties"]["paragraph_plan"][
                "minItems"
            ],
            4,
        )
        self.assertEqual(
            openai_helper.ANALYSIS_SCHEMA["properties"]["paragraph_plan"][
                "maxItems"
            ],
            4,
        )
        self.assertIn("not hidden chain-of-thought", openai_helper.ANALYSIS_RULES)

    def test_inspectable_analysis_output_round_trips(self):
        analysis = CoverLetterAnalysis.model_validate(analysis_payload())

        decoded = CoverLetterAnalysis.model_validate_json(
            analysis.model_dump_json()
        )

        self.assertEqual(decoded, analysis)
        self.assertEqual(decoded.angles[0].id, "reliable_builder")
        self.assertEqual(decoded.paragraph_plan[3].paragraph, 4)
        self.assertIn(
            "production on-call",
            decoded.excluded_claims[0].claim,
        )

    def test_analysis_helper_passes_structured_context_without_network(self):
        expected = analysis_payload()
        resume = {"skills": [{"category": "Programming", "items": ["Python"]}]}

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(expected), {}),
        ) as structured_response:
            result = openai_helper.analyze_cover_letter(
                resume_data=resume,
                job_post="Complete job description",
                company="Example GmbH",
                position="AI Engineer",
                source_url="https://example.com/jobs/ai-engineer",
                instructions="Keep it concise.",
            )

        self.assertEqual(result, expected)
        call = structured_response.call_args.kwargs
        self.assertEqual(call["schema_name"], "cover_letter_analysis")
        self.assertEqual(call["context"]["resume"], resume)
        self.assertEqual(call["context"]["known_company"], "Example GmbH")
        self.assertEqual(call["context"]["known_position"], "AI Engineer")
        self.assertEqual(
            call["context"]["source_url"],
            "https://example.com/jobs/ai-engineer",
        )
        json.dumps(call["context"])

    def test_analysis_normalizes_an_unknown_recommendation_to_first_angle(self):
        expected = analysis_payload()
        expected["recommended_angle_id"] = "unknown_angle"

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(expected), {}),
        ):
            result = openai_helper.analyze_cover_letter(
                resume_data={"skills": []},
                job_post="Complete job description",
            )

        self.assertEqual(result["recommended_angle_id"], "reliable_builder")

    def test_analysis_endpoint_uses_selected_resume_in_temporary_database(self):
        expected = analysis_payload()
        resume = {"about_me": "Candidate summary", "skills": []}

        with tempfile.TemporaryDirectory(prefix="cover-letter-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                connection = sqlite3.connect(db_path)
                cursor = connection.execute(
                    """
                    INSERT INTO resume_versions (name, data, is_current)
                    VALUES (?, ?, ?)
                    """,
                    ("Test resume", json.dumps(resume), 1),
                )
                resume_id = cursor.lastrowid
                connection.commit()
                connection.close()

                request_model = CoverLetterAnalyzeRequest(
                    resume_version_id=resume_id,
                    job_post="Detailed role requirements " * 5,
                    company="Example GmbH",
                    position="AI Engineer",
                )
                with mock.patch.object(
                    cover_letter_routes,
                    "run_cover_letter_analysis",
                    return_value=copy.deepcopy(expected),
                ) as analyze:
                    response = cover_letter_routes.analyze_cover_letter(request_model)

        self.assertIsInstance(response, CoverLetterAnalysis)
        self.assertEqual(response.model_dump(mode="json"), expected)
        self.assertEqual(analyze.call_args.kwargs["resume_data"], resume)


class CompanyResearchSanitizationTests(unittest.TestCase):
    def test_citations_enrich_titles_without_expanding_search_allow_list(self):
        consulted_url = (
            "https://www.Example.com/official/news/?utm_source=search&a=1#release"
        )
        payload = {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "title": "Search result title",
                                "url": consulted_url,
                            },
                        ],
                    },
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Research result",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "title": "Official release title",
                                        "url": "https://example.com/official/news?a=1",
                                    },
                                },
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "title": "Annotation-only source",
                                        "url": "https://example.com/unconsulted",
                                    },
                                },
                            ],
                        },
                    ],
                },
            ],
        }

        sources = openai_helper._consulted_web_sources(payload)

        self.assertEqual(
            sources,
            [
                {
                    "title": "Official release title",
                    "url": consulted_url,
                },
            ],
        )

    def test_only_exact_canonical_allow_list_urls_can_support_insights(self):
        consulted_url = (
            "https://www.Example.com/news/?b=2&utm_source=newsletter&a=1#details"
        )
        research = {
            "status": "completed",
            "summary": "The model's untrusted summary.",
            "insights": [
                {
                    "fact": "Supported fact",
                    "relevance": "Relevant to the role",
                    "source_title": "Model-provided title",
                    "source_url": "https://example.com/news?a=1&b=2",
                },
                {
                    "fact": "Unsupported same-host fact",
                    "relevance": "Should be removed",
                    "source_title": "Another page",
                    "source_url": "https://example.com/unconsulted",
                },
                {
                    "fact": "Unsupported external fact",
                    "relevance": "Should be removed",
                    "source_title": "Untrusted",
                    "source_url": "https://untrusted.example/fact",
                },
            ],
            "sources": [
                {
                    "title": "Model-provided title",
                    "url": "https://example.com/news?a=1&b=2",
                },
                {
                    "title": "Unconsulted page",
                    "url": "https://example.com/unconsulted",
                },
            ],
        }

        sanitized = openai_helper.sanitize_company_research(
            research,
            allowed_urls=[consulted_url],
        )

        self.assertEqual(len(sanitized["insights"]), 1)
        self.assertEqual(sanitized["insights"][0]["fact"], "Supported fact")
        self.assertEqual(sanitized["insights"][0]["source_url"], consulted_url)
        self.assertEqual(sanitized["status"], "limited")
        self.assertEqual(
            sanitized["summary"],
            "Supported fact.",
        )
        self.assertEqual(
            [source["url"] for source in sanitized["sources"]],
            [consulted_url],
        )

    def test_sanitized_research_caps_insights_and_sources(self):
        allowed_urls = [
            f"https://example.com/source/{index}" for index in range(6)
        ]
        research = {
            "status": "completed",
            "summary": "Ignored",
            "insights": [
                {
                    "fact": f"Fact {index}",
                    "relevance": "Relevant",
                    "source_title": f"Source {index}",
                    "source_url": url,
                }
                for index, url in enumerate(allowed_urls)
            ],
            "sources": [
                {"title": f"Source {index}", "url": url}
                for index, url in enumerate(allowed_urls)
            ],
        }

        sanitized = openai_helper.sanitize_company_research(
            research,
            allowed_urls=allowed_urls,
        )

        self.assertEqual(len(sanitized["insights"]), 4)
        self.assertEqual(len(sanitized["sources"]), 5)
        self.assertEqual(sanitized["status"], "completed")

    def test_research_helper_allows_only_sources_reported_by_web_search(self):
        consulted_url = "https://example.com/official/news"
        model_result = {
            "status": "completed",
            "summary": "Untrusted summary",
            "insights": [
                {
                    "fact": "A verified product fact",
                    "relevance": "Useful context",
                    "source_title": "Invented title",
                    "source_url": consulted_url,
                },
                {
                    "fact": "An unsupported fact",
                    "relevance": "Should disappear",
                    "source_title": "Unconsulted page",
                    "source_url": "https://example.com/other",
                },
            ],
            "sources": [
                {"title": "Invented title", "url": consulted_url},
                {
                    "title": "Unconsulted page",
                    "url": "https://example.com/other",
                },
            ],
        }
        response_payload = {
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {
                                "title": "Official product announcement",
                                "url": consulted_url,
                            },
                        ],
                    },
                },
            ],
        }

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(model_result, response_payload),
        ) as structured_response:
            result = openai_helper.research_company(
                company="Example GmbH",
                position="AI Engineer",
                role_summary="Build AI-assisted products.",
            )

        self.assertEqual(len(result["insights"]), 1)
        self.assertEqual(
            result["insights"][0]["source_title"],
            "Official product announcement",
        )
        self.assertEqual(
            [source["url"] for source in result["sources"]],
            [consulted_url],
        )
        call = structured_response.call_args.kwargs
        self.assertEqual(call["tools"], [{"type": "web_search"}])
        self.assertEqual(call["tool_choice"], "required")
        self.assertIn("web_search_call.action.sources", call["include"])


class OpenAIRequestRetryTests(unittest.TestCase):
    @staticmethod
    def http_error(status):
        return urllib_error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=status,
            msg="request failed",
            hdrs={},
            fp=io.BytesIO(
                json.dumps(
                    {"error": {"message": f"temporary error {status}"}}
                ).encode("utf-8")
            ),
        )

    @staticmethod
    def successful_response():
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"output_text":"ok"}'
        return response

    def test_transient_rate_and_server_errors_retry_with_store_disabled(self):
        for status in (429, 503):
            with self.subTest(status=status):
                with (
                    mock.patch.dict(
                        openai_helper.os.environ,
                        {"OPENAI_API_KEY": "test-key"},
                    ),
                    mock.patch.object(
                        openai_helper.request,
                        "urlopen",
                        side_effect=[
                            self.http_error(status),
                            self.successful_response(),
                        ],
                    ) as urlopen,
                    mock.patch.object(openai_helper.time, "sleep") as sleep,
                ):
                    result = openai_helper._request_responses(
                        {
                            "model": "test-model",
                            "input": "test input",
                            "store": True,
                        }
                    )

                self.assertEqual(result, {"output_text": "ok"})
                self.assertEqual(urlopen.call_count, 2)
                sleep.assert_called_once()
                sent_request = urlopen.call_args_list[0].args[0]
                sent_body = json.loads(sent_request.data.decode("utf-8"))
                self.assertIs(sent_body["store"], False)

    def test_non_transient_client_error_is_not_retried(self):
        with (
            mock.patch.dict(
                openai_helper.os.environ,
                {"OPENAI_API_KEY": "test-key"},
            ),
            mock.patch.object(
                openai_helper.request,
                "urlopen",
                side_effect=self.http_error(400),
            ) as urlopen,
            mock.patch.object(openai_helper.time, "sleep") as sleep,
        ):
            with self.assertRaises(ValueError):
                openai_helper._request_responses({"input": "test input"})

        urlopen.assert_called_once()
        sleep.assert_not_called()


class DeterministicCoverLetterValidationTests(unittest.TestCase):
    def test_accepts_word_count_boundaries_with_four_paragraphs(self):
        for counts in ((55, 55, 55, 55), (72, 71, 71, 71)):
            with self.subTest(total=sum(counts)):
                openai_helper.validate_cover_letter(valid_letter(counts))

    def test_rejects_any_paragraph_count_other_than_four(self):
        for paragraph_count in (3, 5):
            with self.subTest(paragraph_count=paragraph_count):
                result = valid_letter()
                result["paragraphs"] = result["paragraphs"][:paragraph_count]
                if paragraph_count == 5:
                    result["paragraphs"].append(paragraph(55))
                with self.assertRaises(ValueError):
                    openai_helper.validate_cover_letter(result)

    def test_rejects_total_word_count_outside_allowed_range(self):
        for counts in ((54, 54, 54, 54), (72, 72, 72, 72)):
            with self.subTest(total=sum(counts)):
                with self.assertRaises(ValueError):
                    openai_helper.validate_cover_letter(valid_letter(counts))

    def test_rejects_a_paragraph_over_eighty_words(self):
        with self.assertRaises(ValueError):
            openai_helper.validate_cover_letter(
                valid_letter((81, 47, 47, 47)),
            )

    def test_rejects_em_dash_in_subject_or_body(self):
        subject_result = valid_letter()
        subject_result["subject"] = "Application — AI Engineer"
        body_result = valid_letter()
        body_result["paragraphs"][2] += " —"

        for location, result in (
            ("subject", subject_result),
            ("body", body_result),
        ):
            with self.subTest(location=location):
                with self.assertRaises(ValueError):
                    openai_helper.validate_cover_letter(result)


class GenerationContextTests(unittest.TestCase):
    def test_generation_helper_remains_compatible_with_legacy_call(self):
        generated = valid_letter()

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(generated), {}),
        ) as structured_response:
            result = openai_helper.generate_cover_letter(
                resume_data={"skills": []},
                job_post="A complete job post",
                current_date="Jul 28th 2026",
            )

        self.assertEqual(result["date"], "Jul 28th 2026")
        context = structured_response.call_args.kwargs["context"]
        self.assertEqual(context["analysis"], "Not provided")
        self.assertEqual(context["validated_company_research"], "Not provided")
        self.assertEqual(context["clarification_answers"], [])
        json.dumps(context)

    def test_generation_uses_requested_angle_when_it_exists(self):
        generated = valid_letter()

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(generated), {}),
        ) as structured_response:
            openai_helper.generate_cover_letter(
                resume_data={"skills": []},
                job_post="A complete job post",
                current_date="Jul 28th 2026",
                analysis=analysis_payload(),
                selected_angle_id="product_collaborator",
            )

        context = structured_response.call_args.kwargs["context"]
        self.assertEqual(context["selected_angle_id"], "product_collaborator")
        self.assertEqual(
            context["selected_angle"]["id"],
            "product_collaborator",
        )

    def test_generation_falls_back_to_recommended_angle_for_unknown_choice(self):
        generated = valid_letter()

        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=(copy.deepcopy(generated), {}),
        ) as structured_response:
            openai_helper.generate_cover_letter(
                resume_data={"skills": []},
                job_post="A complete job post",
                current_date="Jul 28th 2026",
                analysis=analysis_payload(),
                selected_angle_id="missing_angle",
            )

        context = structured_response.call_args.kwargs["context"]
        self.assertEqual(context["selected_angle_id"], "reliable_builder")
        self.assertEqual(context["selected_angle"]["id"], "reliable_builder")

    def test_router_hands_off_and_persists_selected_angle(self):
        resume = {"about_me": "Candidate summary", "skills": []}
        generated = {
            **valid_letter(),
            "date": "Jul 28th 2026",
        }

        with tempfile.TemporaryDirectory(prefix="cover-letter-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                connection = sqlite3.connect(db_path)
                cursor = connection.execute(
                    """
                    INSERT INTO resume_versions (name, data, is_current)
                    VALUES (?, ?, ?)
                    """,
                    ("Test resume", json.dumps(resume), 1),
                )
                resume_id = cursor.lastrowid
                connection.commit()
                connection.close()

                request_model = CoverLetterGenerateRequest(
                    resume_version_id=resume_id,
                    job_post="Detailed role requirements " * 5,
                    company="Example GmbH",
                    position="AI Engineer",
                    analysis=analysis_payload(),
                    selected_angle_id="product_collaborator",
                )
                with (
                    mock.patch.object(
                        cover_letter_routes,
                        "generate_cover_letter",
                        return_value=copy.deepcopy(generated),
                    ) as generate,
                    mock.patch.object(
                        cover_letter_routes,
                        "cover_letter_page_count",
                        return_value=1,
                    ),
                ):
                    response = cover_letter_routes.create_cover_letter(
                        request_model
                    )

        self.assertEqual(
            generate.call_args.kwargs["selected_angle_id"],
            "product_collaborator",
        )
        self.assertEqual(
            response.generation_context.selected_angle_id,
            "product_collaborator",
        )
        self.assertEqual(
            response.generation_context.analysis.angles[1].id,
            "product_collaborator",
        )

    def test_router_persists_effective_angle_when_request_is_unknown(self):
        resume = {"about_me": "Candidate summary", "skills": []}
        generated = {
            **valid_letter(),
            "date": "Jul 28th 2026",
        }

        with tempfile.TemporaryDirectory(prefix="cover-letter-tests-") as temp_dir:
            db_path = str(Path(temp_dir) / "resume.db")
            with mock.patch.object(database, "DB_PATH", db_path):
                database.init_db()
                connection = sqlite3.connect(db_path)
                cursor = connection.execute(
                    """
                    INSERT INTO resume_versions (name, data, is_current)
                    VALUES (?, ?, ?)
                    """,
                    ("Test resume", json.dumps(resume), 1),
                )
                resume_id = cursor.lastrowid
                connection.commit()
                connection.close()

                request_model = CoverLetterGenerateRequest(
                    resume_version_id=resume_id,
                    job_post="Detailed role requirements " * 5,
                    company="Example GmbH",
                    position="AI Engineer",
                    analysis=analysis_payload(),
                    selected_angle_id="unknown_angle",
                )
                with (
                    mock.patch.object(
                        cover_letter_routes,
                        "generate_cover_letter",
                        return_value=copy.deepcopy(generated),
                    ) as generate,
                    mock.patch.object(
                        cover_letter_routes,
                        "cover_letter_page_count",
                        return_value=1,
                    ),
                ):
                    response = cover_letter_routes.create_cover_letter(
                        request_model
                    )

        self.assertEqual(
            generate.call_args.kwargs["selected_angle_id"],
            "reliable_builder",
        )
        self.assertEqual(
            response.generation_context.selected_angle_id,
            "reliable_builder",
        )

    def test_generation_context_round_trips_and_legacy_rows_still_load(self):
        context = CoverLetterGenerationContext.model_validate(
            {
                "source_url": "https://example.com/jobs/ai-engineer",
                "instructions": "Focus on product collaboration.",
                "analysis": analysis_payload(),
                "research": {
                    "status": "limited",
                    "summary": "A verified product fact.",
                    "insights": [
                        {
                            "fact": "A verified product fact",
                            "relevance": "Useful context",
                            "source_title": "Official page",
                            "source_url": "https://example.com/product",
                        },
                    ],
                    "sources": [
                        {
                            "title": "Official page",
                            "url": "https://example.com/product",
                        },
                    ],
                },
                "answers": [
                    {
                        "question_id": "company_motivation",
                        "question": "Why this company?",
                        "answer": "The product problem matches work I enjoy.",
                    },
                ],
                "selected_angle_id": "reliable_builder",
            }
        )
        encoded_context = context.model_dump_json()
        decoded_context = CoverLetterGenerationContext.model_validate_json(
            encoded_context
        )
        self.assertEqual(decoded_context, context)

        base_row = {
            "id": 1,
            "resume_version_id": 2,
            "resume_version_name": "Test resume",
            "company": "Example GmbH",
            "position": "AI Engineer",
            "source_url": None,
            "job_post": "Complete job post",
            "content": json.dumps(content_payload()),
            "created_at": "2026-07-28 12:00:00",
            "updated_at": None,
        }
        legacy_letter = cover_letter_routes._serialize(base_row)
        self.assertIsInstance(legacy_letter, CoverLetter)
        self.assertIsNone(legacy_letter.generation_context)

        legacy_analysis = analysis_payload()
        for field in (
            "observations",
            "angles",
            "recommended_angle_id",
            "paragraph_plan",
            "excluded_claims",
        ):
            legacy_analysis.pop(field)
        saved_legacy_context = cover_letter_routes._serialize(
            {
                **base_row,
                "generation_context": json.dumps(
                    {
                        "analysis": legacy_analysis,
                        "answers": [],
                    }
                ),
            }
        ).generation_context
        self.assertEqual(saved_legacy_context.analysis.observations, [])
        self.assertEqual(saved_legacy_context.analysis.angles, [])
        self.assertEqual(saved_legacy_context.analysis.paragraph_plan, [])
        self.assertEqual(saved_legacy_context.analysis.excluded_claims, [])
        self.assertIsNone(saved_legacy_context.selected_angle_id)

        contextual_row = {
            **base_row,
            "generation_context": encoded_context,
        }
        contextual_letter = cover_letter_routes._serialize(contextual_row)
        self.assertEqual(contextual_letter.generation_context, context)


if __name__ == "__main__":
    unittest.main()
