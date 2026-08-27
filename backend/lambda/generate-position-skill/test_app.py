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
        boto3_module = types.ModuleType("boto3")
        dynamodb_module = types.ModuleType("boto3.dynamodb")
        conditions_module = types.ModuleType("boto3.dynamodb.conditions")

        class FakeKey:
            def __init__(self, name):
                self.name = name

            def eq(self, value):
                return (self.name, value)

        conditions_module.Key = FakeKey
        dynamodb_module.conditions = conditions_module
        boto3_module.dynamodb = dynamodb_module
        sys.modules.setdefault("boto3", boto3_module)
        sys.modules.setdefault("boto3.dynamodb", dynamodb_module)
        sys.modules.setdefault("boto3.dynamodb.conditions", conditions_module)

        botocore_module = types.ModuleType("botocore")
        exceptions_module = types.ModuleType("botocore.exceptions")
        exceptions_module.BotoCoreError = type("BotoCoreError", (Exception,), {})
        exceptions_module.ClientError = type("ClientError", (Exception,), {})
        botocore_module.exceptions = exceptions_module
        sys.modules.setdefault("botocore", botocore_module)
        sys.modules.setdefault("botocore.exceptions", exceptions_module)

        global app
        app = importlib.import_module("app")

    def test_load_positions_from_csv_keeps_master_registration_behavior(self):
        positions = app._load_positions_from_csv(
            _csv_bytes(position_name="HRマネージャー（人事部）")
        )

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["positionId"], "POS00003260")
        self.assertEqual(positions[0]["positionName"], "HRマネージャー")
        self.assertEqual(positions[0]["organizationName"], "人事部")
        self.assertEqual(positions[0]["businessUnitName"], "Corporate")
        self.assertEqual(
            positions[0]["organizationId"],
            app._build_organization_id("人事部", "Corporate"),
        )
        self.assertEqual(
            positions[0]["duties"][0], {"name": "人材育成計画を策定する", "weight": 40}
        )
        self.assertEqual(
            positions[0]["requiredSkills"],
            ["人材育成", "予算管理", "コミュニケーション"],
        )

    def test_load_positions_from_csv_keeps_non_matching_parentheses(self):
        positions = app._load_positions_from_csv(
            _csv_bytes(position_name="ストラテジスト（海外事業）")
        )

        self.assertEqual(positions[0]["positionName"], "ストラテジスト（海外事業）")

    def test_level_rules_include_strict_evaluation_policy(self):
        rules = app._load_level_rules()

        self.assertIn("根拠のない断定をしない", rules)
        self.assertIn("甘い評価に寄せない", rules)
        self.assertIn("ポジションの強みとして要求されるスキル", rules)
        self.assertIn("要求されないまたは低い水準で足りるスキル", rules)
        self.assertIn("ランク、クラス、役職、等級", rules)

    def test_load_skill_master_scans_pages_and_rejects_duplicates(self):
        table = FakeTable(
            scan_pages=[
                {
                    "Items": [{"skillId": "s2", "skillName": "予算管理"}],
                    "LastEvaluatedKey": {"skillId": "s2"},
                },
                {"Items": [{"skillId": "s1", "skillName": "人材育成"}]},
            ]
        )
        fake_boto3 = FakeBoto3(tables={"SkillMaster": table})
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            skills = app._load_skill_master("SkillMaster")
        finally:
            app.boto3 = original_boto3

        self.assertEqual(
            skills,
            [
                {"skillId": "s2", "skillName": "予算管理"},
                {"skillId": "s1", "skillName": "人材育成"},
            ],
        )
        self.assertEqual(table.scan_calls, 2)

        duplicate_table = FakeTable(
            scan_pages=[
                {
                    "Items": [
                        {"skillId": "s1", "skillName": "A"},
                        {"skillId": "s1", "skillName": "B"},
                    ]
                }
            ]
        )
        fake_boto3 = FakeBoto3(tables={"SkillMaster": duplicate_table})
        app.boto3 = fake_boto3
        try:
            with self.assertRaisesRegex(ValueError, "Duplicate skillId"):
                app._load_skill_master("SkillMaster")
        finally:
            app.boto3 = original_boto3

    def test_load_skill_master_rejects_empty_after_invalid_items(self):
        fake_boto3 = FakeBoto3(
            tables={
                "SkillMaster": FakeTable(
                    scan_pages=[{"Items": [{"skillId": "", "skillName": "空"}]}]
                )
            }
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            with self.assertRaisesRegex(ValueError, "SkillMaster is empty"):
                app._load_skill_master("SkillMaster")
        finally:
            app.boto3 = original_boto3

    def test_sort_and_split_skill_master_are_stable(self):
        skills = _skill_master(106)
        reversed_skills = list(reversed(skills))
        sorted_skills = app._sort_skill_master(reversed_skills)
        batches = app._split_skill_batches(sorted_skills, 50)

        self.assertEqual(
            [skill["skillId"] for skill in sorted_skills],
            [skill["skillId"] for skill in skills],
        )
        self.assertEqual([len(batch) for batch in batches], [50, 50, 6])
        self.assertEqual(batches[0][0]["skillId"], "s000")
        self.assertEqual(batches[1][0]["skillId"], "s050")
        self.assertEqual(batches[2][0]["skillId"], "s100")

    def test_load_batch_size_defaults_and_rejects_invalid_values(self):
        self.assertEqual(app._load_batch_size(None), 50)
        self.assertEqual(app._load_batch_size(""), 50)
        self.assertEqual(app._load_batch_size("2"), 2)
        for value in ["0", "-1", "abc"]:
            with self.assertRaisesRegex(ValueError, "POSITION_SKILL_BATCH_SIZE"):
                app._load_batch_size(value)

    def test_evaluate_skill_batch_sends_skill_names_only_and_uses_prompt_cache(self):
        bedrock = FakeBedrockClient(
            [_bedrock_payload({"levels": [0, 4, 3]}, input_tokens=11, output_tokens=5)]
        )
        fake_boto3 = FakeBoto3(bedrock=bedrock)
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            result = app._evaluate_skill_batch(
                "model-id", "level rules", _position(), _skill_master(3)
            )
        finally:
            app.boto3 = original_boto3

        request_body = json.loads(bedrock.requests[0]["body"])
        self.assertEqual(request_body["anthropic_version"], "bedrock-2023-05-31")
        self.assertEqual(request_body["max_tokens"], 1000)
        self.assertNotIn("temperature", request_body)
        content = request_body["messages"][0]["content"]
        self.assertEqual(content[0]["cache_control"], {"type": "ephemeral"})
        self.assertNotIn("cache_control", content[1])
        payload_text = content[1]["text"]
        self.assertIn('"skills": ["スキル000", "スキル001", "スキル002"]', payload_text)
        self.assertNotIn("reason", payload_text)
        payload = json.loads(payload_text[payload_text.rindex("\n{") + 1 :])
        self.assertEqual(payload["skills"], ["スキル000", "スキル001", "スキル002"])
        self.assertTrue(all(isinstance(skill, str) for skill in payload["skills"]))
        self.assertEqual(
            result["skillLevels"],
            [
                {"skillId": "s000", "skillName": "スキル000", "level": 0},
                {"skillId": "s001", "skillName": "スキル001", "level": 4},
                {"skillId": "s002", "skillName": "スキル002", "level": 3},
            ],
        )
        self.assertEqual(result["usage"]["inputTokens"], 11)
        self.assertEqual(result["usage"]["outputTokens"], 5)

    def test_parse_levels_json_validates_contract_strictly(self):
        self.assertEqual(
            app._parse_levels_json('{"levels":[0,1,2,3,4,5]}', 6),
            {"levels": [0, 1, 2, 3, 4, 5]},
        )
        invalid_payloads = [
            ('{"levels":"bad"}', "array"),
            ('{"levels":[1]}', "count"),
            ('{"levels":[1,2],"extra":true}', "only levels"),
            ('{"levels":[true]}', "integers"),
            ('{"levels":["3"]}', "integers"),
            ('{"levels":[1.0]}', "integers"),
            ('{"levels":[null]}', "integers"),
            ('{"levels":[6]}', "integers"),
        ]
        for payload, message in invalid_payloads:
            with self.assertRaisesRegex(ValueError, message):
                app._parse_levels_json(payload, 1 if message != "count" else 2)

    def test_invoke_bedrock_rejects_max_tokens_before_parsing(self):
        bedrock = FakeBedrockClient(
            [_bedrock_payload({"levels": [1]}, stop_reason="max_tokens")]
        )
        fake_boto3 = FakeBoto3(bedrock=bedrock)
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            with self.assertRaisesRegex(ValueError, "max_tokens"):
                app._invoke_bedrock(
                    "model-id",
                    [{"type": "text", "text": "rules"}],
                    lambda _text: self.fail("parser must not run"),
                )
        finally:
            app.boto3 = original_boto3

    def test_evaluate_all_skill_levels_merges_batches_and_usage(self):
        bedrock = FakeBedrockClient(
            [
                _bedrock_payload(
                    {"levels": [0, 1]},
                    input_tokens=10,
                    output_tokens=2,
                    cache_creation_input_tokens=3,
                    cache_read_input_tokens=4,
                ),
                _bedrock_payload(
                    {"levels": [5]},
                    input_tokens=20,
                    output_tokens=3,
                    cache_creation_input_tokens=1,
                    cache_read_input_tokens=2,
                ),
            ]
        )
        fake_boto3 = FakeBoto3(bedrock=bedrock)
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            result = app._evaluate_all_skill_levels(
                "model-id",
                "level rules",
                _position(),
                [_skill_master(2), _skill_master(3)[2:]],
            )
        finally:
            app.boto3 = original_boto3

        self.assertEqual([item["level"] for item in result["skillLevels"]], [0, 1, 5])
        self.assertEqual(result["usage"]["inputTokens"], 30)
        self.assertEqual(result["usage"]["outputTokens"], 5)
        self.assertEqual(result["usage"]["totalTokens"], 35)
        self.assertEqual(result["usage"]["cacheCreationInputTokens"], 4)
        self.assertEqual(result["usage"]["cacheReadInputTokens"], 6)
        self.assertEqual(result["usage"]["batchCount"], 2)
        self.assertEqual(result["usage"]["evaluatedCount"], 3)

    def test_validate_complete_skill_levels_rejects_missing_extra_and_duplicates(self):
        skills = _skill_master(2)
        app._validate_complete_skill_levels(
            skills,
            [
                {"skillId": "s000", "skillName": "スキル000", "level": 0},
                {"skillId": "s001", "skillName": "スキル001", "level": 5},
            ],
        )
        invalid_results = [
            [{"skillId": "s000", "skillName": "スキル000", "level": 1}],
            [
                {"skillId": "s000", "skillName": "スキル000", "level": 1},
                {"skillId": "s000", "skillName": "スキル000", "level": 2},
            ],
            [
                {"skillId": "s001", "skillName": "スキル001", "level": 1},
                {"skillId": "s000", "skillName": "スキル000", "level": 2},
            ],
            [
                {"skillId": "s000", "skillName": "スキル000", "level": True},
                {"skillId": "s001", "skillName": "スキル001", "level": 2},
            ],
        ]
        for result in invalid_results:
            with self.assertRaises(ValueError):
                app._validate_complete_skill_levels(skills, result)

    def test_save_position_skill_levels_saves_all_skills_including_zero_without_metadata(
        self,
    ):
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
                    {"skillId": "s000", "skillName": "スキル000", "level": 0},
                    {"skillId": "s001", "skillName": "スキル001", "level": 5},
                ],
            )
        finally:
            app.boto3 = original_boto3

        self.assertEqual(count, 2)
        self.assertEqual(table.items[0]["level"], 0)
        self.assertNotIn("reason", table.items[0])
        self.assertNotIn("usage", table.items[0])
        self.assertNotIn("stop_reason", table.items[0])

    def test_delete_stale_position_skill_levels_only_after_success_path_helper(self):
        table = FakeTable(
            query_pages=[
                {
                    "Items": [
                        {"positionId": "POS00003260", "skillId": "s000"},
                        {"positionId": "POS00003260", "skillId": "old"},
                    ]
                }
            ]
        )
        fake_boto3 = FakeBoto3(tables={"PositionSkill": table})
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            deleted_count = app._delete_stale_position_skill_levels(
                "PositionSkill", "POS00003260", _skill_master(1)
            )
        finally:
            app.boto3 = original_boto3

        self.assertEqual(deleted_count, 1)
        self.assertEqual(
            table.deleted_keys, [{"positionId": "POS00003260", "skillId": "old"}]
        )

    def test_handler_saves_only_after_all_batches_succeed(self):
        os.environ["BEDROCK_MODEL_ID"] = "model-id"
        os.environ["S3_BUCKET_NAME"] = "bucket"
        os.environ["SKILL_MASTER_TABLE_NAME"] = "SkillMaster"
        os.environ["POSITION_SKILL_TABLE_NAME"] = "PositionSkill"
        os.environ["ORGANIZATION_MASTER_TABLE_NAME"] = "OrganizationMaster"
        os.environ["POSITION_MASTER_TABLE_NAME"] = "PositionMaster"
        os.environ["POSITION_SKILL_BATCH_SIZE"] = "2"
        position_skill_table = FakeTable(query_pages=[{"Items": []}])
        fake_boto3 = FakeBoto3(
            s3=FakeS3Client(_csv_bytes()),
            bedrock=FakeBedrockClient(
                [
                    _bedrock_payload({"levels": [0, 4]}),
                    _bedrock_payload({"levels": [3]}),
                ]
            ),
            tables={
                "SkillMaster": FakeTable(scan_pages=[{"Items": _skill_master(3)}]),
                "PositionSkill": position_skill_table,
                "OrganizationMaster": FakeTable(),
                "PositionMaster": FakeTable(),
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
            os.environ.pop("POSITION_SKILL_BATCH_SIZE", None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["positionCount"], 1)
        self.assertEqual(body["skillMasterCount"], 3)
        self.assertEqual(body["evaluatedCount"], 3)
        self.assertEqual(len(position_skill_table.items), 3)
        self.assertEqual(
            [item["level"] for item in position_skill_table.items], [0, 4, 3]
        )
        self.assertEqual(len(fake_boto3.bedrock.requests), 2)

    def test_handler_does_not_save_position_skills_when_later_batch_fails(self):
        os.environ["BEDROCK_MODEL_ID"] = "model-id"
        os.environ["S3_BUCKET_NAME"] = "bucket"
        os.environ["SKILL_MASTER_TABLE_NAME"] = "SkillMaster"
        os.environ["POSITION_SKILL_TABLE_NAME"] = "PositionSkill"
        os.environ["ORGANIZATION_MASTER_TABLE_NAME"] = "OrganizationMaster"
        os.environ["POSITION_MASTER_TABLE_NAME"] = "PositionMaster"
        os.environ["POSITION_SKILL_BATCH_SIZE"] = "2"
        position_skill_table = FakeTable(query_pages=[{"Items": []}])
        fake_boto3 = FakeBoto3(
            s3=FakeS3Client(_csv_bytes()),
            bedrock=FakeBedrockClient(
                [
                    _bedrock_payload({"levels": [0, 4]}),
                    _bedrock_payload({"levels": [3, 2]}),
                ]
            ),
            tables={
                "SkillMaster": FakeTable(scan_pages=[{"Items": _skill_master(3)}]),
                "PositionSkill": position_skill_table,
                "OrganizationMaster": FakeTable(),
                "PositionMaster": FakeTable(),
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
            os.environ.pop("POSITION_SKILL_BATCH_SIZE", None)

        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(position_skill_table.items, [])
        self.assertEqual(position_skill_table.deleted_keys, [])


def _csv_bytes(position_name="HRマネージャー"):
    return (
        "ポジションコード,ポジション名,CXO・BU名,組織名,"
        "主な職務#1,主な職務#1 関与度(%),"
        "主な職務#2,主な職務#2 関与度(%),"
        "主な職務#3,主な職務#3 関与度(%),"
        "主な職務#4,主な職務#4 関与度(%),"
        "主な職務#5,主な職務#5 関与度(%),"
        "必要知識・スキル(知識・スキル)\n"
        f"POS00003260,{position_name},Corporate,人事部,"
        "人材育成計画を策定する,40,予算を管理する,30,,,,,,,"
        "人材育成、予算管理、コミュニケーション\n"
    ).encode("utf-8-sig")


def _position():
    return {
        "positionId": "POS00003260",
        "positionName": "HRマネージャー",
        "businessUnitName": "Corporate",
        "organizationName": "人事部",
        "organizationId": app._build_organization_id("人事部", "Corporate"),
        "duties": [
            {"name": "人材育成計画を策定する", "weight": 40},
            {"name": "予算を管理する", "weight": 30},
        ],
        "requiredSkills": ["人材育成", "予算管理", "コミュニケーション"],
    }


def _skill_master(count):
    return [
        {"skillId": f"s{index:03}", "skillName": f"スキル{index:03}"}
        for index in range(count)
    ]


def _bedrock_payload(
    content,
    input_tokens=10,
    output_tokens=5,
    cache_creation_input_tokens=2,
    cache_read_input_tokens=1,
    stop_reason="end_turn",
):
    return {
        "content": [{"type": "text", "text": json.dumps(content, ensure_ascii=False)}],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "cache_read_input_tokens": cache_read_input_tokens,
        },
        "stop_reason": stop_reason,
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

    def delete_item(self, Key):  # pylint: disable=invalid-name
        self.table.deleted_keys.append(Key)


class FakeTable:
    def __init__(self, scan_pages=None, query_pages=None):
        self.scan_pages = list(scan_pages or [])
        self.query_pages = list(query_pages or [])
        self.scan_calls = 0
        self.query_calls = 0
        self.items = []
        self.deleted_keys = []

    def scan(self, **_kwargs):
        page = self.scan_pages[self.scan_calls]
        self.scan_calls += 1
        return page

    def query(self, **_kwargs):
        self.query_calls += 1
        return self.query_pages.pop(0) if self.query_pages else {"Items": []}

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
