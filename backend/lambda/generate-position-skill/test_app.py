import importlib
import json
import os
import sys
import types
import unittest
from io import BytesIO


class GeneratePositionSkillTest(unittest.TestCase):
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

        global app
        app = importlib.import_module("app")

    def test_load_positions_from_csv_reads_required_columns(self):
        positions = app._load_positions_from_csv(_csv_bytes())

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["positionId"], "POS00003260")
        self.assertEqual(positions[0]["positionName"], "HRマネージャー")
        self.assertEqual(positions[0]["businessUnitName"], "Corporate")
        self.assertEqual(positions[0]["organizationName"], "人事部")
        self.assertEqual(
            positions[0]["duties"],
            [
                {"name": "人材育成計画を策定する", "weight": 40},
                {"name": "予算を管理する", "weight": 30},
            ],
        )
        self.assertEqual(
            positions[0]["requiredSkills"],
            ["人材育成", "予算管理", "コミュニケーション"],
        )

    def test_load_skill_master_scans_all_pages(self):
        fake_boto3 = FakeBoto3(
            tables={
                "SkillMaster": FakeTable(
                    scan_pages=[
                        {
                            "Items": [{"skillId": "s1", "skillName": "人材育成"}],
                            "LastEvaluatedKey": {"skillId": "s1"},
                        },
                        {"Items": [{"skillId": "s2", "skillName": "予算管理"}]},
                    ]
                )
            }
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            skills = app._load_skill_master("SkillMaster")
        finally:
            app.boto3 = original_boto3

        self.assertEqual(
            skills,
            [
                {"skillId": "s1", "skillName": "人材育成"},
                {"skillId": "s2", "skillName": "予算管理"},
            ],
        )

    def test_extract_candidate_skills_uses_prompt_cache_and_usage(self):
        fake_boto3 = FakeBoto3(
            bedrock=FakeBedrockClient(
                [
                    _bedrock_payload(
                        {"candidate_skills": ["人材育成", "予算管理", "人材育成"]},
                        input_tokens=11,
                        output_tokens=7,
                        cache_creation_input_tokens=5,
                        cache_read_input_tokens=3,
                    )
                ]
            )
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            result = app._extract_candidate_skills(
                "model-id",
                "candidate rules",
                _position(),
                [
                    {"skillId": "s1", "skillName": "人材育成"},
                    {"skillId": "s2", "skillName": "予算管理"},
                ],
            )
        finally:
            app.boto3 = original_boto3

        request_body = json.loads(fake_boto3.bedrock.requests[0]["body"])
        content = request_body["messages"][0]["content"]
        self.assertEqual(content[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", content[1])
        self.assertEqual(result["candidate_skills"], ["人材育成", "予算管理"])
        self.assertEqual(result["usage"]["inputTokens"], 11)
        self.assertEqual(result["usage"]["outputTokens"], 7)
        self.assertEqual(result["usage"]["cacheCreationInputTokens"], 5)
        self.assertEqual(result["usage"]["cacheReadInputTokens"], 3)
        self.assertEqual(result["stopReason"], "end_turn")

    def test_validate_candidate_skills_removes_unknown_and_duplicates(self):
        candidates = app._validate_candidate_skills(
            ["人材育成", "未知スキル", "人材育成", "予算管理"],
            [
                {"skillId": "s1", "skillName": "人材育成"},
                {"skillId": "s2", "skillName": "予算管理"},
            ],
        )

        self.assertEqual(
            candidates,
            [
                {"skillId": "s1", "skillName": "人材育成"},
                {"skillId": "s2", "skillName": "予算管理"},
            ],
        )

    def test_evaluate_skill_levels_uses_prompt_cache_and_usage(self):
        fake_boto3 = FakeBoto3(
            bedrock=FakeBedrockClient(
                [
                    _bedrock_payload(
                        {
                            "position_id": "POS00003260",
                            "skill_levels": [
                                {"skill_name": "人材育成", "level": 4},
                                {"skill_name": "予算管理", "level": 3},
                            ],
                        },
                        input_tokens=13,
                        output_tokens=9,
                        cache_creation_input_tokens=6,
                        cache_read_input_tokens=4,
                    )
                ]
            )
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            result = app._evaluate_skill_levels(
                "model-id",
                "level rules",
                _position(),
                [
                    {"skillId": "s1", "skillName": "人材育成"},
                    {"skillId": "s2", "skillName": "予算管理"},
                ],
            )
        finally:
            app.boto3 = original_boto3

        request_body = json.loads(fake_boto3.bedrock.requests[0]["body"])
        content = request_body["messages"][0]["content"]
        self.assertEqual(content[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", content[1])
        self.assertEqual(
            result["skill_levels"],
            [
                {"skill_name": "人材育成", "level": 4},
                {"skill_name": "予算管理", "level": 3},
            ],
        )
        self.assertEqual(result["usage"]["inputTokens"], 13)
        self.assertEqual(result["usage"]["outputTokens"], 9)

    def test_save_position_skill_levels_writes_without_reason(self):
        table = FakeTable()
        fake_boto3 = FakeBoto3(tables={"PositionSkill": table})
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            count = app._save_position_skill_levels(
                "PositionSkill",
                "bucket",
                "position-input/sample.csv",
                _position(),
                [
                    {"skillId": "s1", "skillName": "人材育成", "level": 4},
                    {"skillId": "s2", "skillName": "予算管理", "level": 3},
                ],
            )
        finally:
            app.boto3 = original_boto3

        self.assertEqual(count, 2)
        self.assertEqual(table.items[0]["positionId"], "POS00003260")
        self.assertEqual(table.items[0]["skillId"], "s1")
        self.assertEqual(table.items[0]["level"], 4)
        self.assertNotIn("reason", table.items[0])

    def test_handler_evaluates_and_saves_positions_without_aws(self):
        os.environ["BEDROCK_MODEL_ID"] = "model-id"
        os.environ["S3_BUCKET_NAME"] = "bucket"
        os.environ["SKILL_MASTER_TABLE_NAME"] = "SkillMaster"
        os.environ["POSITION_SKILL_TABLE_NAME"] = "PositionSkill"
        position_table = FakeTable()
        fake_boto3 = FakeBoto3(
            s3=FakeS3Client(_csv_bytes()),
            bedrock=FakeBedrockClient(
                [
                    _bedrock_payload({"candidate_skills": ["人材育成", "予算管理"]}),
                    _bedrock_payload(
                        {
                            "position_id": "POS00003260",
                            "skill_levels": [
                                {"skill_name": "人材育成", "level": 4},
                                {"skill_name": "予算管理", "level": 3},
                            ],
                        },
                    ),
                ]
            ),
            tables={
                "SkillMaster": FakeTable(
                    scan_pages=[
                        {
                            "Items": [
                                {"skillId": "s1", "skillName": "人材育成"},
                                {"skillId": "s2", "skillName": "予算管理"},
                            ]
                        }
                    ]
                ),
                "PositionSkill": position_table,
            },
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            response = app.handler(
                {"bucket": "bucket", "key": "position-input/sample.csv"}, None
            )
        finally:
            app.boto3 = original_boto3

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["position_count"], 1)
        self.assertEqual(body["saved_count"], 2)
        self.assertEqual(len(position_table.items), 2)
        self.assertEqual(len(fake_boto3.bedrock.requests), 2)


def _csv_bytes():
    return (
        "ポジションコード,ポジション名,CXO・BU名,組織名,"
        "主な職務#1,主な職務#1 関与度(%),"
        "主な職務#2,主な職務#2 関与度(%),"
        "主な職務#3,主な職務#3 関与度(%),"
        "主な職務#4,主な職務#4 関与度(%),"
        "主な職務#5,主な職務#5 関与度(%),"
        "必要知識・スキル(知識・スキル)\n"
        "POS00003260,HRマネージャー,Corporate,人事部,"
        "人材育成計画を策定する,40,予算を管理する,30,,,,,,,"
        "人材育成、予算管理、コミュニケーション\n"
    ).encode("utf-8-sig")


def _position():
    return {
        "positionId": "POS00003260",
        "positionName": "HRマネージャー",
        "businessUnitName": "Corporate",
        "organizationName": "人事部",
        "duties": [
            {"name": "人材育成計画を策定する", "weight": 40},
            {"name": "予算を管理する", "weight": 30},
        ],
        "requiredSkills": ["人材育成", "予算管理", "コミュニケーション"],
    }


def _bedrock_payload(
    content,
    input_tokens=10,
    output_tokens=5,
    cache_creation_input_tokens=2,
    cache_read_input_tokens=1,
):
    return {
        "content": [{"type": "text", "text": json.dumps(content, ensure_ascii=False)}],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
        },
        "stop_reason": "end_turn",
    }


class FakeBody:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class FakeS3Client:
    def __init__(self, csv_bytes):
        self.csv_bytes = csv_bytes

    def get_object(self, Bucket, Key):  # pylint: disable=invalid-name
        return {"Body": BytesIO(self.csv_bytes)}


class FakeBedrockClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def invoke_model(self, **kwargs):
        self.requests.append(kwargs)
        return {"body": FakeBody(self.payloads.pop(0))}


class FakeBatchWriter:
    def __init__(self, table):
        self.table = table

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return False

    def put_item(self, Item):  # pylint: disable=invalid-name
        self.table.items.append(Item)


class FakeTable:
    def __init__(self, scan_pages=None):
        self.scan_pages = list(scan_pages or [])
        self.scan_calls = 0
        self.items = []

    def scan(self, **_kwargs):
        page = self.scan_pages[self.scan_calls]
        self.scan_calls += 1
        return page

    def batch_writer(self):
        return FakeBatchWriter(self)


class FakeDynamoDBResource:
    def __init__(self, tables):
        self.tables = tables

    def Table(self, table_name):  # pylint: disable=invalid-name
        return self.tables[table_name]


class FakeBoto3:
    def __init__(self, s3=None, bedrock=None, tables=None):
        self.s3 = s3
        self.bedrock = bedrock
        self.tables = tables or {}

    def client(self, service_name):
        if service_name == "s3":
            return self.s3
        if service_name == "bedrock-runtime":
            return self.bedrock
        raise AssertionError(f"Unexpected client: {service_name}")

    def resource(self, service_name):
        if service_name == "dynamodb":
            return FakeDynamoDBResource(self.tables)
        raise AssertionError(f"Unexpected resource: {service_name}")


if __name__ == "__main__":
    unittest.main()
