import sys
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.messages import AIMessage


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import ai_helper
import openai_helper


class LangChainGeminiTests(unittest.TestCase):
    def test_suggestion_uses_the_compiled_langgraph(self):
        with mock.patch.object(
            ai_helper.GEMINI_GRAPH,
            "invoke",
            return_value={"result": AIMessage(content="Improved text")},
        ) as invoke:
            result = ai_helper.suggest_improvement(
                "about_me",
                "Original text",
                feedback="Keep it direct",
            )

        self.assertEqual(result, "Improved text")
        state = invoke.call_args.args[0]
        self.assertEqual(state["provider"], "gemini")
        self.assertEqual(state["max_tokens"], 500)
        self.assertEqual(state["messages"][0].type, "system")
        self.assertIn("Original text", state["messages"][1].content)
        self.assertIn("Keep it direct", state["messages"][1].content)

    def test_chatgpt_selection_is_forwarded_to_the_shared_graph(self):
        with mock.patch.object(
            ai_helper.AI_GRAPH,
            "invoke",
            return_value={"result": AIMessage(content="ChatGPT result")},
        ) as invoke:
            result = ai_helper.suggest_improvement(
                "about_me",
                "Original text",
                provider="chatgpt",
            )

        self.assertEqual(result, "ChatGPT result")
        self.assertEqual(invoke.call_args.args[0]["provider"], "chatgpt")


class ResumeAIProviderTests(unittest.TestCase):
    def test_chatgpt_model_uses_the_configured_resume_model(self):
        with mock.patch.dict(ai_helper.os.environ, {"OPENAI_API_KEY": "test-key"}):
            model = ai_helper._get_model(provider="chatgpt", max_tokens=500)

        self.assertEqual(model.model_name, ai_helper.OPENAI_RESUME_MODEL)
        self.assertTrue(model.use_responses_api)
        self.assertFalse(model.store)

    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported AI provider"):
            ai_helper._get_model(provider="other", max_tokens=500)


class LangChainOpenAITests(unittest.TestCase):
    def test_model_configuration_uses_responses_api_and_framework_retries(self):
        with mock.patch.dict(
            openai_helper.os.environ,
            {"OPENAI_API_KEY": "test-key"},
        ):
            model = openai_helper._get_openai_model("test-model")

        self.assertEqual(model.model_name, "test-model")
        self.assertTrue(model.use_responses_api)
        self.assertEqual(model.max_retries, openai_helper.OPENAI_MAX_ATTEMPTS)
        self.assertFalse(model.store)

    def test_structured_node_converts_web_search_tool_for_langchain(self):
        raw = AIMessage(content="")
        structured = mock.MagicMock()
        structured.invoke.return_value = {
            "parsed": {"answer": "ok"},
            "raw": raw,
            "parsing_error": None,
        }
        model = mock.MagicMock()
        model.with_structured_output.return_value = structured

        with mock.patch.object(
            openai_helper,
            "_get_openai_model",
            return_value=model,
        ):
            result = openai_helper._invoke_structured_model(
                {
                    "instructions": "Return JSON.",
                    "context": {"input": "value"},
                    "schema": {
                        "title": "answer",
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                        "required": ["answer"],
                    },
                    "tools": [{"type": "web_search"}],
                    "tool_choice": "required",
                }
            )

        self.assertEqual(result["result"], {"answer": "ok"})
        call = model.with_structured_output.call_args
        self.assertEqual(call.kwargs["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(call.kwargs["method"], "json_schema")
        self.assertTrue(call.kwargs["include_raw"])

    def test_gemini_structured_output_never_builds_an_openai_model(self):
        raw = AIMessage(content="Grounded company facts")
        structured = mock.MagicMock()
        structured.invoke.return_value = {
            "parsed": {"answer": "ok"},
            "raw": AIMessage(content='{"answer":"ok"}'),
            "parsing_error": None,
        }
        gemini_model = mock.MagicMock()
        gemini_model.invoke.return_value = raw
        gemini_model.with_structured_output.return_value = structured

        with (
            mock.patch.object(
                openai_helper,
                "_get_gemini_model",
                return_value=gemini_model,
            ) as get_gemini,
            mock.patch.object(openai_helper, "_get_openai_model") as get_openai,
        ):
            result = openai_helper._invoke_structured_model(
                {
                    "provider": "gemini",
                    "instructions": "Return JSON.",
                    "context": {"company": "Example"},
                    "schema": {
                        "title": "answer",
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                        "required": ["answer"],
                    },
                    "tools": [{"type": "web_search"}],
                }
            )

        self.assertEqual(result["result"], {"answer": "ok"})
        self.assertIs(result["raw"], raw)
        get_gemini.assert_called_once()
        get_openai.assert_not_called()
        gemini_model.invoke.assert_called_once()
        self.assertEqual(
            gemini_model.invoke.call_args.kwargs["tools"],
            [{"google_search": {}}],
        )

    def test_cover_letter_analysis_forwards_gemini_provider(self):
        with mock.patch.object(
            openai_helper,
            "_structured_response",
            return_value=({}, AIMessage(content="")),
        ) as structured:
            openai_helper.analyze_cover_letter(
                resume_data={"about_me": "Example"},
                job_post="Example role",
                provider="gemini",
            )

        self.assertEqual(structured.call_args.kwargs["provider"], "gemini")

    def test_gemini_grounding_metadata_becomes_the_source_allow_list(self):
        message = AIMessage(
            content="Grounded answer",
            response_metadata={
                "grounding_metadata": {
                    "grounding_chunks": [
                        {
                            "web": {
                                "title": "Official source",
                                "uri": "https://example.com/news",
                            }
                        }
                    ]
                }
            },
        )

        self.assertEqual(
            openai_helper._consulted_web_sources(message),
            [
                {
                    "title": "Official source",
                    "url": "https://example.com/news",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
