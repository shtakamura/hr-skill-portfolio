import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_taxonomy_context.py"


def _load_taxonomy_builder():
    spec = importlib.util.spec_from_file_location("build_taxonomy_context", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
            {"skills": [f"スキル{i}" for i in range(count)]},
            ensure_ascii=False,
        )

    def test_build_taxonomy_context_converts_categories_and_subcategories(self):
        builder = _load_taxonomy_builder()

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "lightcast_skill_subcategories.csv"
            output_path = Path(temp_dir) / "taxonomy_context.md"
            source_path.write_text(
                "category,subcategory\n"
                "Analysis,Data Analysis\n"
                "Analysis,Data Visualization\n"
                "Business,Project Management\n",
                encoding="utf-8",
            )

            category_count, subcategory_count = builder.build_taxonomy_context(
                source_path, output_path
            )

            self.assertEqual(category_count, 2)
            self.assertEqual(subcategory_count, 3)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Lightcast Skill Taxonomy", content)
            self.assertIn("## Analysis", content)
            self.assertIn("- Data Analysis", content)
            self.assertIn("- Data Visualization", content)
            self.assertIn("## Business", content)
            self.assertIn("- Project Management", content)

    def test_build_taxonomy_context_skips_empty_and_duplicate_rows(self):
        builder = _load_taxonomy_builder()

        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "lightcast_skill_subcategories.csv"
            output_path = Path(temp_dir) / "taxonomy_context.md"
            source_path.write_bytes(
                (
                    "\ufeffcategory,subcategory\n"
                    "Analysis,Data Analysis\n"
                    "Analysis,Data Analysis\n"
                    "Analysis,\n"
                    ",Project Management\n"
                    "Business, Project Management \n"
                ).encode("utf-8")
            )

            category_count, subcategory_count = builder.build_taxonomy_context(
                source_path, output_path
            )

            self.assertEqual(category_count, 2)
            self.assertEqual(subcategory_count, 2)
            content = output_path.read_text(encoding="utf-8")
            self.assertEqual(content.count("- Data Analysis"), 1)
            self.assertEqual(content.count("- Project Management"), 1)
            self.assertNotIn("�", content)

    def test_load_rules_reads_japanese_rules_without_mojibake(self):
        import app

        rules = app._load_rules()

        self.assertIn("スキル件数に上限を設けない", rules)
        self.assertIn("有効なJSON", rules)
        self.assertIn("日本語", rules)
        self.assertNotIn("�", rules)

    def test_load_taxonomy_context_reads_generated_context(self):
        import app

        taxonomy_context = app._load_taxonomy_context()

        self.assertIn("# Lightcast スキルタクソノミー（日本語訳）", taxonomy_context)
        self.assertIn("## 分析", taxonomy_context)
        self.assertIn("- データ分析", taxonomy_context)
        self.assertNotIn("�", taxonomy_context)

    def test_load_taxonomy_context_rejects_missing_file(self):
        import app

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(
                ValueError, "Unable to read taxonomy_context.md"
            ):
                app._load_taxonomy_context(Path(temp_dir) / "missing.md")

    def test_load_taxonomy_context_rejects_empty_file(self):
        import app

        with tempfile.TemporaryDirectory() as temp_dir:
            taxonomy_path = Path(temp_dir) / "taxonomy_context.md"
            taxonomy_path.write_text("  \n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "taxonomy_context.md is empty"):
                app._load_taxonomy_context(taxonomy_path)

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

    def test_build_bedrock_content_splits_cached_fixed_context_and_dynamic_records(
        self,
    ):
        import app

        content = app._build_bedrock_content(
            "RULES_TEXT",
            "# Lightcast Skill Taxonomy\n\n## Analysis\n\n- Data Analysis",
            {"duties": ["分析"], "required_skills": ["統計"]},
        )

        self.assertEqual(len(content), 2)
        fixed_block = content[0]
        dynamic_block = content[1]
        self.assertEqual(fixed_block["type"], "text")
        self.assertEqual(fixed_block["cache_control"], {"type": "ephemeral"})
        self.assertIn("RULES_TEXT", fixed_block["text"])
        self.assertIn("# Lightcast Skill Taxonomy", fixed_block["text"])
        self.assertEqual(dynamic_block["type"], "text")
        self.assertNotIn("cache_control", dynamic_block)
        self.assertIn('"duties": ["分析"]', dynamic_block["text"])
        self.assertNotIn("RULES_TEXT", dynamic_block["text"])
        self.assertNotIn("Lightcast Skill Taxonomy", dynamic_block["text"])

    def test_real_rules_provide_lightcast_policy_and_output_contract(self):
        import app

        content = app._build_bedrock_content(
            app._load_rules(),
            "# Lightcast Skill Taxonomy\n\n## Analysis\n\n- Data Analysis",
            {"duties": ["分析"], "required_skills": ["統計"]},
        )
        fixed_text = content[0]["text"]

        self.assertIn("Lightcast Skill Taxonomyを、スキル名称の標準化", fixed_text)
        self.assertIn("自然な日本語のスキル名", fixed_text)
        self.assertIn("スキル名だけをJSONで返す", fixed_text)
        self.assertIn("definitionは生成しない", fixed_text)
        self.assertIn("制度名、規格名、手法名、組織機能名、成果名、KPI名", fixed_text)
        self.assertIn("能力・専門性を抽出する", fixed_text)
        self.assertIn("評価対象となる能力を表現する", fixed_text)
        self.assertIn("過度に抽象化", fixed_text)
        self.assertIn("近接するサブカテゴリ", fixed_text)
        self.assertIn("接尾語が違うだけ", fixed_text)
        self.assertIn("制度や規格を含む名称を許容する", fixed_text)
        self.assertIn("スキル数を減らすこと自体を目的にしない", fixed_text)

    def test_parse_skill_master_json_accepts_one_skill_name(self):
        import app

        skill_master = app._parse_skill_master_json('{"skills":["プロジェクト管理"]}')

        self.assertEqual(skill_master, {"skills": ["プロジェクト管理"]})

    def test_parse_skill_master_json_accepts_21_skill_names(self):
        import app

        skill_master = app._parse_skill_master_json(self._skill_json(21))

        self.assertEqual(len(skill_master["skills"]), 21)

    def test_parse_skill_master_json_accepts_50_skill_names(self):
        import app

        skill_master = app._parse_skill_master_json(self._skill_json(50))

        self.assertEqual(len(skill_master["skills"]), 50)

    def test_parse_skill_master_json_rejects_missing_skills(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output does not contain 'skills'"
        ):
            app._parse_skill_master_json(
                '{"items":["分析"]}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_parse_skill_master_json_rejects_skills_dict(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output 'skills' must be an array"
        ):
            app._parse_skill_master_json(
                '{"skills":{"name":"分析"}}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_parse_skill_master_json_rejects_empty_skills(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Generated skills count must be at least 1"
        ):
            app._parse_skill_master_json('{"skills": []}')

    def test_parse_skill_master_json_excludes_empty_strings(self):
        import app

        skill_master = app._parse_skill_master_json(
            '{"skills":["", "  ", "データ分析"]}'
        )

        self.assertEqual(skill_master, {"skills": ["データ分析"]})

    def test_parse_skill_master_json_normalizes_and_deduplicates_skill_names(self):
        import app

        skill_master = app._parse_skill_master_json(
            json.dumps(
                {"skills": [" データ  分析 ", "データ 分析", "ＡＩ  活用", "AI 活用"]},
                ensure_ascii=False,
            )
        )

        self.assertEqual(skill_master, {"skills": ["データ 分析", "AI 活用"]})

    def test_parse_skill_master_json_keeps_partial_matches_separate(self):
        import app

        skill_master = app._parse_skill_master_json(
            json.dumps(
                {"skills": ["データ分析", "データ分析基盤設計"]}, ensure_ascii=False
            )
        )

        self.assertEqual(skill_master["skills"], ["データ分析", "データ分析基盤設計"])

    def test_parse_skill_master_json_rejects_old_skill_object_format(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output 'skills' entries must be strings"
        ):
            app._parse_skill_master_json(
                '{"skills":[{"skill_name":"分析","definition":"分析する能力"}]}'
            )

    def test_parse_skill_master_json_rejects_skill_master_wrapper(self):
        import app

        with self.assertRaisesRegex(
            ValueError, "Bedrock output does not contain 'skills'"
        ):
            app._parse_skill_master_json(
                '{"skill_master":{"skills":["分析"]}}',
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 2},
            )

    def test_extract_bedrock_text_concatenates_multiple_text_blocks(self):
        import app

        self.assertEqual(
            app._extract_bedrock_text(
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

    def test_parse_skill_master_json_accepts_fenced_and_prefixed_json(self):
        import app

        skill_master = app._parse_skill_master_json(
            '以下です。```json\n{"skills":["データ分析"]}\n```以上です。'
        )

        self.assertEqual(skill_master, {"skills": ["データ分析"]})

    def test_parse_skill_master_json_rejects_truncated_json(self):
        import app

        with self.assertRaises(json.JSONDecodeError):
            app._parse_skill_master_json('{"skills":["データ分析"')

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

    def test_invoke_bedrock_uses_anthropic_request_and_prompt_cache_content(self):
        import app

        captured_request = {}
        generated_text = self._skill_json(1)

        class BedrockRuntimeClient:
            def invoke_model(self, **kwargs):
                captured_request.update(kwargs)
                return {
                    "body": BytesIO(
                        json.dumps(
                            {
                                "content": [{"type": "text", "text": generated_text}],
                                "usage": {
                                    "input_tokens": 12,
                                    "output_tokens": 8,
                                    "cache_creation_input_tokens": 100,
                                    "cache_read_input_tokens": 200,
                                },
                                "stop_reason": "end_turn",
                            },
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                }

        content = app._build_bedrock_content(
            "RULES_TEXT",
            "# Lightcast Skill Taxonomy\n\n## Analysis\n\n- Data Analysis",
            {"duties": ["分析"], "required_skills": ["統計"]},
        )
        app.boto3.client = lambda service_name: BedrockRuntimeClient()

        skill_master = app._invoke_bedrock(
            "jp.anthropic.claude-sonnet-4-5-20250929-v1:0", content
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
        self.assertEqual(request_body["max_tokens"], 3000)
        request_content = request_body["messages"][0]["content"]
        self.assertEqual(request_content[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", request_content[1])
        self.assertIn("RULES_TEXT", request_content[0]["text"])
        self.assertIn('"duties": ["分析"]', request_content[1]["text"])
        self.assertEqual(skill_master["skills"], ["スキル0"])
        self.assertEqual(
            skill_master["usage"],
            {
                "inputTokens": 12,
                "outputTokens": 8,
                "totalTokens": 20,
                "cacheCreationInputTokens": 100,
                "cacheReadInputTokens": 200,
            },
        )
        self.assertEqual(skill_master["stopReason"], "end_turn")

    def test_invoke_bedrock_rejects_max_tokens_without_parsing(self):
        import app

        class BedrockRuntimeClient:
            def invoke_model(self, **_kwargs):
                return {
                    "body": BytesIO(
                        json.dumps(
                            {
                                "content": [{"type": "text", "text": "not json"}],
                                "usage": {"input_tokens": 12, "output_tokens": 3000},
                                "stop_reason": "max_tokens",
                            },
                            ensure_ascii=False,
                        ).encode("utf-8")
                    )
                }

        app.boto3.client = lambda service_name: BedrockRuntimeClient()

        with self.assertLogs(level="WARNING") as log_context:
            with self.assertRaisesRegex(
                ValueError,
                "Bedrock output was truncated because max_tokens was reached",
            ):
                app._invoke_bedrock("model-id", "prompt text")

        self.assertIn(
            "Bedrock output may have been truncated because max_tokens was reached",
            "\n".join(log_context.output),
        )

    def test_extract_bedrock_usage_defaults_invalid_cache_values_to_zero(self):
        import app

        self.assertEqual(
            app._extract_bedrock_usage(
                {
                    "usage": {
                        "input_tokens": "x",
                        "output_tokens": -1,
                        "cache_creation_input_tokens": True,
                    }
                }
            ),
            {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "cacheCreationInputTokens": 0,
                "cacheReadInputTokens": 0,
            },
        )
        self.assertEqual(
            app._extract_bedrock_usage({}),
            {
                "inputTokens": 0,
                "outputTokens": 0,
                "totalTokens": 0,
                "cacheCreationInputTokens": 0,
                "cacheReadInputTokens": 0,
            },
        )

    def test_handler_response_includes_usage_and_stop_reason_without_saving_them(self):
        import app

        captured_request = {}
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
                                "content": [
                                    {
                                        "type": "text",
                                        "text": '{"skills":["データ分析"]}',
                                    }
                                ],
                                "usage": {
                                    "input_tokens": 3,
                                    "output_tokens": 4,
                                    "cache_creation_input_tokens": 5,
                                    "cache_read_input_tokens": 6,
                                },
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

        with self.assertLogs(level="INFO") as log_context:
            response = app.handler({"key": "input.csv"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            body["usage"],
            {
                "inputTokens": 3,
                "outputTokens": 4,
                "totalTokens": 7,
                "cacheCreationInputTokens": 5,
                "cacheReadInputTokens": 6,
            },
        )
        self.assertEqual(body["stopReason"], "end_turn")
        self.assertEqual(body["saved_count"], 1)
        self.assertEqual(len(saved_items), 1)
        self.assertEqual(saved_items[0]["skillName"], "データ分析")
        self.assertNotIn("definition", saved_items[0])
        self.assertNotIn("usage", saved_items[0])
        self.assertNotIn("stopReason", saved_items[0])
        self.assertIn(
            "Bedrock usage: input_tokens=3 output_tokens=4 total_tokens=7 cache_creation_input_tokens=5 cache_read_input_tokens=6 stop_reason=end_turn saved_count=1",
            "\n".join(log_context.output),
        )

        request_body = json.loads(captured_request["body"])
        request_content = request_body["messages"][0]["content"]
        self.assertIn("有効なJSON", request_content[0]["text"])
        self.assertIn("Lightcast Skill Taxonomy", request_content[0]["text"])
        self.assertIn('"skills"', request_content[0]["text"])
        self.assertIn('"duties": ["分析"]', request_content[1]["text"])
        self.assertNotIn("definition", request_content[1]["text"])


if __name__ == "__main__":
    unittest.main()
