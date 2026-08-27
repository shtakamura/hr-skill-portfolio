import importlib
import json
import os
import sys
import types
import unittest
from decimal import Decimal


class CalculateSimilarityTest(unittest.TestCase):
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

    def setUp(self):
        os.environ["POSITION_SKILL_TABLE_NAME"] = "PositionSkill"
        os.environ["POSITION_MASTER_TABLE_NAME"] = "PositionMaster"
        os.environ["CORS_ALLOW_ORIGIN"] = "https://example.cloudfront.net"

    def test_core_skill_keys_use_mean_plus_standard_deviation(self):
        skills = [
            {"skillId": "A", "level": 5},
            {"skillId": "B", "level": 4},
            {"skillId": "C", "level": 1},
            {"skillId": "D", "level": 0},
        ]

        self.assertEqual(app._core_skill_keys(skills), {("A", 5)})

    def test_jaccard_similarity(self):
        self.assertEqual(
            app._jaccard_similarity(
                {("A", 5), ("B", 4), ("C", 3), ("D", 2)},
                {("A", 5), ("C", 3), ("E", 1)},
            ),
            0.4,
        )
        self.assertEqual(app._jaccard_similarity(set(), set()), 0.0)

    def test_same_skill_with_different_level_is_not_a_core_match(self):
        self.assertEqual(
            app._jaccard_similarity({("Leadership", 5)}, {("Leadership", 4)}), 0.0
        )

    def test_group_position_skills_excludes_invalid_levels_and_bool(self):
        grouped = app._group_position_skills(
            [
                {"positionId": "P1", "skillId": "B", "skillName": "B", "level": 4},
                {
                    "positionId": "P1",
                    "skillId": "A",
                    "skillName": "A",
                    "level": Decimal("5"),
                },
                {
                    "positionId": "P2",
                    "skillId": "bad",
                    "skillName": "bad",
                    "level": True,
                },
                {
                    "positionId": "P2",
                    "skillId": "bad2",
                    "skillName": "bad2",
                    "level": 9,
                },
            ]
        )

        self.assertEqual([skill["skillId"] for skill in grouped["P1"]], ["A", "B"])
        self.assertNotIn("P2", grouped)

    def test_rank_similar_positions_excludes_selected_and_limits_top9(self):
        skills_by_position = {
            "P000": _skills([5, 4, 1, 0]),
            "P001": _skills([5, 4, 0, 0]),
            "P002": _skills([0, 0, 5, 4]),
            **{f"P{index:03}": _skills([5, 0, 0, 0]) for index in range(3, 25)},
        }
        names = {
            position_id: f"ポジション{position_id}"
            for position_id in skills_by_position
        }

        results = app._rank_similar_positions(
            "P000",
            app._core_skill_keys(skills_by_position["P000"]),
            skills_by_position,
            names,
        )

        self.assertEqual(len(results), 9)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[0]["positionId"], "P001")
        self.assertNotIn("P000", [result["positionId"] for result in results])

    def test_chart_skills_are_top10_by_level_then_skill_name(self):
        skills = [
            {"skillId": f"s{index}", "skillName": skill_name, "level": level}
            for index, (skill_name, level) in enumerate(
                [
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

        chart_skills = app._chart_skills(skills)

        self.assertEqual(len(chart_skills), 10)
        self.assertEqual([skill["skillName"] for skill in chart_skills[:2]], ["A", "B"])
        self.assertNotIn("K", [skill["skillName"] for skill in chart_skills])

    def test_handler_returns_ranked_similarity_without_aws(self):
        fake_boto3 = FakeBoto3(
            {
                "PositionSkill": FakeTable(
                    scan_pages=[
                        {
                            "Items": [
                                *_position_skill_items("P001", [5, 4, 1, 0]),
                                *_position_skill_items("P002", [5, 4, 0, 0]),
                            ],
                            "LastEvaluatedKey": {"page": 1},
                        },
                        {"Items": [*_position_skill_items("P003", [0, 0, 5, 4])]},
                    ]
                ),
                "PositionMaster": FakeTable(
                    scan_pages=[
                        {
                            "Items": [
                                {
                                    "positionId": "P001",
                                    "positionName": "選択ポジション",
                                },
                                {
                                    "positionId": "P002",
                                    "positionName": "近いポジション",
                                },
                                {
                                    "positionId": "P003",
                                    "positionName": "遠いポジション",
                                },
                            ]
                        }
                    ]
                ),
            }
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            response = app.handler(
                {"queryStringParameters": {"positionId": "P001"}}, None
            )
        finally:
            app.boto3 = original_boto3

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertTrue(body["dataFound"])
        self.assertEqual(body["selectedPositionId"], "P001")
        self.assertEqual(
            body["results"][0],
            {
                "rank": 1,
                "positionId": "P002",
                "positionName": "近いポジション",
                "organizationName": "組織P002",
                "businessUnitName": "BUP002",
                "similarityScore": 1.0,
                "chartSkills": [
                    {"skillId": "S0", "skillName": "スキル0", "level": 5},
                    {"skillId": "S1", "skillName": "スキル1", "level": 4},
                    {"skillId": "S2", "skillName": "スキル2", "level": 0},
                    {"skillId": "S3", "skillName": "スキル3", "level": 0},
                ],
            },
        )
        self.assertEqual(body["results"][1]["positionId"], "P003")

    def test_handler_returns_no_data_when_selected_position_has_no_skills(self):
        fake_boto3 = FakeBoto3(
            {
                "PositionSkill": FakeTable(
                    scan_pages=[{"Items": _position_skill_items("P002", [5])}]
                ),
                "PositionMaster": FakeTable(scan_pages=[{"Items": []}]),
            }
        )
        original_boto3 = app.boto3
        app.boto3 = fake_boto3
        try:
            response = app.handler(
                {"queryStringParameters": {"positionId": "P001"}}, None
            )
        finally:
            app.boto3 = original_boto3

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertFalse(body["dataFound"])
        self.assertEqual(body["results"], [])

    def test_handler_requires_position_id(self):
        response = app.handler({"queryStringParameters": {}}, None)

        self.assertEqual(response["statusCode"], 400)


def _skills(levels):
    return [
        {
            "skillId": chr(ord("A") + index),
            "skillName": chr(ord("A") + index),
            "level": level,
        }
        for index, level in enumerate(levels)
    ]


def _position_skill_items(position_id, levels):
    return [
        {
            "positionId": position_id,
            "skillId": f"S{index}",
            "skillName": f"スキル{index}",
            "organizationName": f"組織{position_id}",
            "businessUnitName": f"BU{position_id}",
            "level": level,
        }
        for index, level in enumerate(levels)
    ]


class FakeTable:
    def __init__(self, scan_pages):
        self.scan_pages = list(scan_pages)
        self.scan_calls = 0

    def scan(self, **_kwargs):
        page = self.scan_pages[self.scan_calls]
        self.scan_calls += 1
        return page


class FakeDynamoDBResource:
    def __init__(self, tables):
        self.tables = tables

    def Table(self, table_name):  # pylint: disable=invalid-name
        return self.tables[table_name]


class FakeBoto3:
    def __init__(self, tables):
        self.tables = tables

    def resource(self, service_name):
        if service_name == "dynamodb":
            return FakeDynamoDBResource(self.tables)
        raise AssertionError(f"Unexpected resource: {service_name}")


if __name__ == "__main__":
    unittest.main()
