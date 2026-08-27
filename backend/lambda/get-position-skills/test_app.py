import importlib
import json
import os
import sys
import types
import unittest
from decimal import Decimal


class GetPositionSkillsTest(unittest.TestCase):
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

    def setUp(self):
        os.environ["POSITION_SKILL_TABLE_NAME"] = "PositionSkill"
        os.environ["CORS_ALLOW_ORIGIN"] = "https://example.cloudfront.net"

    def test_gets_position_skills_by_position_id_without_scan(self):
        table = FakeTable([{"Items": _items("POS00005648")}])
        self._with_table(table)

        response = app.handler(
            {"queryStringParameters": {"positionId": " POS00005648 "}}, None
        )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(body["dataFound"])
        self.assertEqual(body["positionId"], "POS00005648")
        self.assertEqual(len(body["skills"]), 3)
        self.assertEqual(table.scan_calls, 0)
        self.assertEqual(table.query_calls, 1)
        self.assertNotIn("IndexName", table.query_kwargs[0])

    def test_returns_data_found_false_when_no_match(self):
        table = FakeTable([{"Items": []}])
        self._with_table(table)

        response = app.handler(
            {"queryStringParameters": {"positionId": "POS00005648"}}, None
        )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertFalse(body["dataFound"])
        self.assertEqual(body["skills"], [])

    def test_rejects_organization_and_position_name_without_position_id(self):
        response = app.handler(
            {
                "queryStringParameters": {
                    "organizationName": "システム開発部",
                    "positionName": "スペシャリスト",
                }
            },
            None,
        )

        self.assertEqual(response["statusCode"], 400)

    def test_sorts_by_level_then_skill_name_and_limits_top_10(self):
        items = [
            {
                "positionId": "POS",
                "skillId": f"s{index}",
                "organizationName": "組織",
                "positionName": "ポジション",
                "skillName": skill_name,
                "level": level,
            }
            for index, (skill_name, level) in enumerate(
                [
                    ("Z", 0),
                    ("K", 1),
                    ("B", 5),
                    ("A", 5),
                    ("C", 4),
                    ("D", 4),
                    ("E", 3),
                    ("F", 3),
                    ("G", 2),
                    ("H", 2),
                    ("I", 1),
                    ("J", 1),
                ]
            )
        ]

        body = app._build_response(items, "POS")

        self.assertEqual(len(body["skills"]), 10)
        self.assertEqual(body["skills"][0]["skillName"], "A")
        self.assertEqual(body["skills"][1]["skillName"], "B")
        self.assertNotIn("K", [skill["skillName"] for skill in body["skills"]])
        self.assertNotIn("Z", [skill["skillName"] for skill in body["skills"]])

    def test_level_zero_records_are_data_found_but_not_chart_skills(self):
        body = app._build_response(
            [
                {
                    "positionId": "POS00005648",
                    "skillId": "s0",
                    "organizationName": "組織",
                    "positionName": "ポジション",
                    "skillName": "不要スキル",
                    "level": 0,
                }
            ],
            "POS00005648",
        )

        self.assertTrue(body["dataFound"])
        self.assertEqual(body["validSkillCount"], 1)
        self.assertEqual(body["skills"], [])

    def test_keeps_less_than_10_valid_skills(self):
        body = app._build_response(_items("POS00005648")[:3], "POS00005648")

        self.assertEqual(len(body["skills"]), 3)

    def test_excludes_invalid_level_and_bool(self):
        items = _items("POS00005648") + [
            {
                "positionId": "POS00005648",
                "skillId": "x",
                "skillName": "不正",
                "level": 6,
            },
            {
                "positionId": "POS00005648",
                "skillId": "y",
                "skillName": "真偽",
                "level": True,
            },
            {
                "positionId": "POS00005648",
                "skillId": "z",
                "skillName": "小数",
                "level": Decimal("1.5"),
            },
        ]

        body = app._build_response(items, "POS00005648")

        self.assertEqual(body["validSkillCount"], 3)
        self.assertEqual(len(body["skills"]), 3)

    def test_rejects_missing_query_parameters(self):
        response = app.handler({"queryStringParameters": {}}, None)

        self.assertEqual(response["statusCode"], 400)

    def _with_table(self, table):
        app.boto3 = FakeBoto3(table)


def _items(position_id):
    return [
        {
            "positionId": position_id,
            "skillId": "s1",
            "organizationName": "カスタマーサポート部",
            "positionName": "ストラテジスト（カスタマーサポート部）",
            "skillName": "業務改善・最適化",
            "level": Decimal("5"),
        },
        {
            "positionId": position_id,
            "skillId": "s2",
            "organizationName": "カスタマーサポート部",
            "positionName": "ストラテジスト（カスタマーサポート部）",
            "skillName": "カスタマーサクセス",
            "level": 4,
        },
        {
            "positionId": position_id,
            "skillId": "s3",
            "organizationName": "カスタマーサポート部",
            "positionName": "ストラテジスト（カスタマーサポート部）",
            "skillName": "VOC分析",
            "level": 4,
        },
    ]


class FakeTable:
    def __init__(self, query_pages):
        self.query_pages = list(query_pages)
        self.query_calls = 0
        self.query_kwargs = []
        self.scan_calls = 0

    def query(self, **kwargs):
        self.query_kwargs.append(kwargs)
        page = self.query_pages[self.query_calls]
        self.query_calls += 1
        return page

    def scan(self, **_kwargs):
        self.scan_calls += 1
        raise AssertionError("PositionSkill API must not scan the table")


class FakeDynamoDBResource:
    def __init__(self, table):
        self.table = table

    def Table(self, _table_name):  # pylint: disable=invalid-name
        return self.table


class FakeBoto3:
    def __init__(self, table):
        self.table = table

    def resource(self, service_name):
        if service_name == "dynamodb":
            return FakeDynamoDBResource(self.table)
        raise AssertionError(f"Unexpected resource: {service_name}")


if __name__ == "__main__":
    unittest.main()
