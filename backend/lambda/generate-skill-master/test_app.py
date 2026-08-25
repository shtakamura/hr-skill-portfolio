import sys
import types
import unittest
from io import BytesIO


class PromptTemplateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules.setdefault("boto3", types.ModuleType("boto3"))

        botocore_module = types.ModuleType("botocore")
        exceptions_module = types.ModuleType("botocore.exceptions")
        exceptions_module.BotoCoreError = type("BotoCoreError", (Exception,), {})
        exceptions_module.ClientError = type("ClientError", (Exception,), {})
        botocore_module.exceptions = exceptions_module
        sys.modules.setdefault("botocore", botocore_module)
        sys.modules.setdefault("botocore.exceptions", exceptions_module)

    def test_prompt_template_format_accepts_records_placeholder(self):
        from app import PROMPT_TEMPLATE

        prompt = PROMPT_TEMPLATE.format(records='{"duties": [], "required_skills": []}')

        self.assertIn('"skills"', prompt)
        self.assertIn('{"duties": [], "required_skills": []}', prompt)

    def test_invoke_bedrock_uses_anthropic_request_and_response_format(self):
        import app

        captured_request = {}

        class BedrockRuntimeClient:
            def invoke_model(self, **kwargs):
                captured_request.update(kwargs)
                return {
                    "body": BytesIO(
                        b'{"content":[{"type":"text","text":"{\\"skills\\":[{\\"skill_name\\":\\"Data Analysis\\",\\"definition\\":\\"Analyze business data\\"}]}"}]}'
                    )
                }

        app.boto3.client = lambda service_name: BedrockRuntimeClient()

        skill_master = app._invoke_bedrock(
            "jp.anthropic.claude-sonnet-4-5-20250929-v1:0", "prompt text"
        )

        self.assertEqual(
            captured_request["modelId"],
            "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        request_body = app.json.loads(captured_request["body"])
        self.assertNotIn("temperature", request_body)
        self.assertNotIn("max_completion_tokens", request_body)
        self.assertNotIn("input", request_body)
        self.assertNotIn("tools", request_body)
        self.assertEqual(
            request_body,
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": "prompt text"}],
            },
        )
        self.assertEqual(
            skill_master,
            {
                "skills": [
                    {
                        "skill_name": "Data Analysis",
                        "definition": "Analyze business data",
                    }
                ]
            },
        )

    def test_extract_bedrock_text_accepts_anthropic_content_text(self):
        from app import _extract_bedrock_text

        self.assertEqual(
            _extract_bedrock_text({"content": [{"type": "text", "text": " result "}]}),
            "result",
        )

    def test_extract_bedrock_text_concatenates_multiple_text_blocks(self):
        from app import _extract_bedrock_text

        self.assertEqual(
            _extract_bedrock_text(
                {
                    "content": [
                        {"type": "text", "text": " first "},
                        {"type": "tool_use", "text": " ignored "},
                        {"type": "text", "text": " second "},
                    ]
                }
            ),
            "first\nsecond",
        )

    def test_parse_skill_master_json_accepts_plain_json(self):
        from app import _parse_skill_master_json

        skill_master = _parse_skill_master_json(
            '{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}]}'
        )

        self.assertEqual(len(skill_master["skills"]), 1)

    def test_parse_skill_master_json_accepts_code_fence_and_one_skill(self):
        from app import _parse_skill_master_json

        skill_master = _parse_skill_master_json(
            '```json\n{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}]}\n```'
        )

        self.assertEqual(
            skill_master,
            {
                "skills": [
                    {
                        "skill_name": "Data Analysis",
                        "definition": "Analyze business data",
                    }
                ]
            },
        )

    def test_parse_skill_master_json_accepts_plain_code_fence(self):
        from app import _parse_skill_master_json

        skill_master = _parse_skill_master_json(
            '```\n{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}]}\n```'
        )

        self.assertEqual(len(skill_master["skills"]), 1)

    def test_parse_skill_master_json_accepts_prefixed_text(self):
        from app import _parse_skill_master_json

        skill_master = _parse_skill_master_json(
            '以下です。{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}]}'
        )

        self.assertEqual(len(skill_master["skills"]), 1)

    def test_parse_skill_master_json_accepts_suffixed_text(self):
        from app import _parse_skill_master_json

        skill_master = _parse_skill_master_json(
            '{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}]}以上です。'
        )

        self.assertEqual(len(skill_master["skills"]), 1)

    def test_parse_skill_master_json_rejects_empty_string(self):
        from app import _parse_skill_master_json

        with self.assertRaises(Exception):
            _parse_skill_master_json("")

    def test_parse_skill_master_json_rejects_truncated_json(self):
        from app import _parse_skill_master_json

        with self.assertRaises(Exception):
            _parse_skill_master_json(
                '{"skills":[{"skill_name":"Data Analysis","definition":"Analyze business data"}'
            )

    def test_parse_skill_master_json_rejects_missing_skills(self):
        from app import _parse_skill_master_json

        with self.assertRaises(ValueError):
            _parse_skill_master_json('{"items": []}')

    def test_prompt_template_includes_strict_output_rules(self):
        from app import PROMPT_TEMPLATE

        self.assertIn("有効なJSONオブジェクトのみを出力する", PROMPT_TEMPLATE)
        self.assertIn("Markdownのコードフェンスを付けない", PROMPT_TEMPLATE)


if __name__ == "__main__":
    unittest.main()
