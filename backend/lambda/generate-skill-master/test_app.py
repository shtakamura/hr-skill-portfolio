import json
import os
import sys
import tempfile
import types
import unittest
from io import BytesIO
from pathlib import Path


class GenerateSkillMasterTest(unittest.TestCase):
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

    def _skill_json(self, count):
        return json.dumps(
            {
                "skills": [
                    {
                        "skill_name": f"スキル{i}",
                        "definition": f"業務上の能力{i}を発揮する能力",
                    }
                    for i in range(count)
                ]
            },
            ensure_ascii=False,
        )

    def test_load_rules_reads_japanese_rules(self):
        import app

        rules = app._load_rules()

        self.assertIn("スキル件数に上限を設けない", rules)
        self.assertIn("有効なJSON", rules)
        self.assertIn("日本語", rules)
        self.assertNotIn("�", rules)

    def test_rules_include_top_level_skills_array_contract(self):
        import app

        rules = app._load_rules()

        self.assertIn("トップレベル項目はskillsのみ", rules)
        self.assertIn("skillsは必ず配列", rules)
        self.assertIn("skill_nameやdefinitionをトップレベルへ出力してはならない", rules)

        json_start = rules.find("{")
        json_end = rules.rfind("}")
        if json_start != -1 and json_end != -1 and json_start < json_end:
            output_example = json.loads(rules[json_start : json_end + 1])
            self.assertEqual(list(output_example.keys()), ["skills"])
            self.assertIsInstance(output_example["skills"], list)
            self.assertGreaterEqual(len(output_example["skills"]), 1)
            self.assertIn("skill_name", output_example["skills"][0])
            self.assertIn("definition", output_example["skills"][0])
        else:
            self.assertIn('"skills"', rules)
            self.assertIn('"skill_name"', rules)
            self.assertIn('"definition"', rules)

    def test_load_rules_reads_utf8_bom_file(self):
        import app

        with tempfile.TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "rules.md"
            rules_path.write_bytes("\ufeff日本語ルール".encode("utf-8"))

            self.assertEqual(app._load_rules(rules_path), "日本語ルール")

    def test_load_rules_rejects_missing_file(self):
        import app

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                app._load_rules(Path(temp_dir) / "missing-rules.md")

    def test_load_rules_rejects_empty_file(self):
        import app

        with tempfile.TemporaryDirectory() as temp_dir:
            rules_path = Path(temp_dir) / "rules.md"
            rules_path.write_text("  \n", encoding="utf-8")

            with self.assertRaises(ValueError):
                app._load_rules(rules_path)

    def test_prompt_template_accepts_rules_and_records_placeholders(self):
        from app import PROMPT_TEMPLATE

        prompt = PROMPT_TEMPLATE.format(
            rules="有効なJSONのみを返す",
            records='{"duties": [], "required_skills": []}',
        )

        self.assertIn("有効なJSON", prompt)
        self.assertIn('{"duties": [], "required_skills": []}', prompt)

    def test_parse_skill_master_json_accepts_one_skill(self):
        import app

        skill_master = app._parse_skill_master_json(self._skill_json(1))

        self.assertEqual(len(skill_master["skills"]), 1)

    def test_parse_skill_master_json_accepts_21_skills(self):
        import app

        skill_master = app._parse_skill_master_json(self._skill_json(21))

        self.assertEqual(len(skill_master["skills"]), 21)

    def test_parse_skill_master_json_accepts_50_skills(self):
        import app

        skill_master = app._parse_skill_master_json(self._skill_json(50))

        self.assertEqual(len(skill_master["skills"]), 50)

    def test_parse_skill_master_json_rejects_zero_skills(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Generated skills count must be at least 1"
        ):
            app._parse_skill_master_json('{"skills": []}')

    def test_parse_skill_master_json_rejects_missing_skills(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output does not contain 'skills'"
        ):
            app._parse_skill_master_json(
                '{"items":[{"skill_name":"分析","definition":"分析する能力"}]}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_parse_skill_master_json_rejects_skills_dict(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output 'skills' must be an array"
        ):
            app._parse_skill_master_json(
                '{"skills":{"skill_name":"分析","definition":"分析する能力"}}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_parse_skill_master_json_rejects_skill_master_wrapper(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output does not contain 'skills'"
        ):
            app._parse_skill_master_json(
                '{"skill_master":{"skills":[{"skill_name":"分析","definition":"分析する能力"}]}}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_unexpected_structure_log_does_not_include_generated_answer_text(self):
        import app

        generated_text = '{"items":[{"secret":"FULL_GENERATED_ANSWER_TEXT"}]}'

        with self.assertLogs(level="WARNING") as log_context:
            with self.assertRaisesRegex(
                ValueError, "Bedrock output does not contain 'skills'"
            ):
                app._parse_skill_master_json(
                    generated_text,
                    stop_reason="end_turn",
                    usage={"input_tokens": 10, "output_tokens": 20},
                )

        log_output = "\n".join(log_context.output)
        self.assertIn("Unexpected Bedrock output structure", log_output)
        self.assertIn("top_level_type=dict", log_output)
        self.assertIn("keys=['items']", log_output)
        self.assertIn("skills_type=missing", log_output)
        self.assertIn(f"generated_text_length={len(generated_text)}", log_output)
        self.assertIn("stop_reason=end_turn", log_output)
        self.assertIn("input_tokens=10", log_output)
        self.assertIn("output_tokens=20", log_output)
        self.assertNotIn("FULL_GENERATED_ANSWER_TEXT", log_output)

    def test_parse_skill_master_json_deduplicates_same_normalized_skill_name(self):
        import app

        skill_master = app._parse_skill_master_json(
            json.dumps(
                {
                    "skills": [
                        {
                            "skill_name": " データ  分析 ",
                            "definition": "業務データを分析する能力",
                        },
                        {
                            "skill_name": "データ 分析",
                            "definition": "別定義は採用しない能力",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(
            skill_master,
            {
                "skills": [
                    {
                        "skill_name": "データ 分析",
                        "definition": "業務データを分析する能力",
                    }
                ]
            },
        )

    def test_parse_skill_master_json_keeps_partial_matches_separate(self):
        import app

        skill_master = app._parse_skill_master_json(
            json.dumps(
                {
                    "skills": [
                        {
                            "skill_name": "データ分析",
                            "definition": "業務データを分析する能力",
                        },
                        {
                            "skill_name": "データ分析基盤設計",
                            "definition": "分析基盤を設計する能力",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        self.assertEqual(len(skill_master["skills"]), 2)

    def test_invoke_bedrock_uses_anthropic_request_and_response_metadata(self):
        import app

        captured_request = {}

        class BedrockRuntimeClient:
            def invoke_model(self, **kwargs):
                captured_request.update(kwargs)
                return {
                    "body": BytesIO(
                        json.dumps(
                            {
                                "content": [
                                    {
                                        "type": "text",
                                        "text": self_text,
                                    }
                                ],
                                "usage": {"input_tokens": 12, "output_tokens": 8},
                                "stop_reason": "end_turn",
                            },
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                }

        self_text = self._skill_json(1)
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
        self.assertEqual(request_body["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(request_body["max_tokens"], 10000)
        self.assertEqual(
            request_body["messages"], [{"role": "user", "content": "prompt text"}]
        )
        self.assertEqual(
            skill_master["usage"],
            {"inputTokens": 12, "outputTokens": 8, "totalTokens": 20},
        )
        self.assertEqual(skill_master["stopReason"], "end_turn")

    def test_extract_bedrock_usage_defaults_invalid_values_to_zero(self):
        import app

        self.assertEqual(
            app._extract_bedrock_usage(
                {"usage": {"input_tokens": "x", "output_tokens": -1}}
            ),
            {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
        )
        self.assertEqual(
            app._extract_bedrock_usage({}),
            {"inputTokens": 0, "outputTokens": 0, "totalTokens": 0},
        )

    def test_invoke_bedrock_warns_when_stop_reason_is_max_tokens(self):
        import app

        skill_json = self._skill_json(1)

        class BedrockRuntimeClient:
            def invoke_model(self, **_kwargs):
                return {
                    "body": BytesIO(
                        json.dumps(
                            {
                                "content": [{"type": "text", "text": skill_json}],
                                "stop_reason": "max_tokens",
                            },
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                }

        app.boto3.client = lambda service_name: BedrockRuntimeClient()

        with self.assertLogs(level="WARNING") as log_context:
            skill_master = app._invoke_bedrock("model-id", "prompt text")

        self.assertEqual(skill_master["stopReason"], "max_tokens")
        self.assertIn(
            "Bedrock output may have been truncated because max_tokens was reached",
            "\n".join(log_context.output),
        )

    def test_handler_response_includes_usage_and_stop_reason_without_saving_them(self):
        import app

        captured_request = {}
        skill_json = self._skill_json(1)
        saved_items = []

        class S3Client:
            def get_object(self, **_kwargs):
                csv_bytes = (
                    "主な職務#1,主な職務#2,主な職務#3,主な職務#4,主な職務#5,必要知識・スキル(知識・スキル)\n"
                    "分析,,,,,統計\n"
                ).encode("utf-8-sig")
                return {"Body": BytesIO(csv_bytes)}

        class BedrockRuntimeClient:
            def invoke_model(self, **kwargs):
                captured_request.update(kwargs)
                return {
                    "body": BytesIO(
                        json.dumps(
                            {
                                "content": [{"type": "text", "text": skill_json}],
                                "usage": {"input_tokens": 3, "output_tokens": 4},
                                "stop_reason": "end_turn",
                            },
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                }

        class BatchWriter:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

            def put_item(self, Item):
                saved_items.append(Item)

        class Table:
            def batch_writer(self):
                return BatchWriter()

        class DynamoDBResource:
            def Table(self, _table_name):
                return Table()

        def client(service_name):
            if service_name == "s3":
                return S3Client()
            if service_name == "bedrock-runtime":
                return BedrockRuntimeClient()
            raise AssertionError(f"Unexpected client: {service_name}")

        app.boto3.client = client
        app.boto3.resource = lambda service_name: DynamoDBResource()
        os.environ["BEDROCK_MODEL_ID"] = "model-id"
        os.environ["S3_BUCKET_NAME"] = "bucket"
        os.environ["SKILL_MASTER_TABLE_NAME"] = "SkillMaster"

        response = app.handler({"key": "input.csv"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            body["usage"], {"inputTokens": 3, "outputTokens": 4, "totalTokens": 7}
        )
        self.assertEqual(body["stopReason"], "end_turn")
        self.assertEqual(body["saved_count"], 1)
        self.assertEqual(len(saved_items), 1)
        self.assertNotIn("usage", saved_items[0])
        self.assertNotIn("stopReason", saved_items[0])
        self.assertIn("日本語", app._load_rules())
        request_body = json.loads(captured_request["body"])
        prompt = request_body["messages"][0]["content"]
        self.assertIn("有効なJSON", prompt)
        self.assertIn('"skills"', prompt)
        self.assertIn('"skill_name"', prompt)
        self.assertIn('"definition"', prompt)


if __name__ == "__main__":
    unittest.main()
