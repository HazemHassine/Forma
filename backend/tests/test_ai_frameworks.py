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
        self.assertEqual(state["max_tokens"], 500)
        self.assertEqual(state["messages"][0].type, "system")
        self.assertIn("Original text", state["messages"][1].content)
        self.assertIn("Keep it direct", state["messages"][1].content)


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


if __name__ == "__main__":
    unittest.main()
