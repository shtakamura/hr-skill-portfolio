import importlib
import json
import os
import sys
import types
import unittest


class GetPositionMasterTest(unittest.TestCase):
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
        os.environ["ORGANIZATION_MASTER_TABLE_NAME"] = "OrganizationMaster"
        os.environ["POSITION_MASTER_TABLE_NAME"] = "PositionMaster"

    def test_get_organizations_scans_master_and_returns_active_items(self):
        fake_boto3 = FakeBoto3(
            {
                "OrganizationMaster": FakeTable(
                    scan_pages=[
                        {
                            "Items": [
                                {
                                    "organizationId": "ORG2",
                                    "organizationName": "営業部",
                                    "businessUnitName": "COO",
                                    "isActive": True,
                                },
                                {
                                    "organizationId": "OLD",
                                    "organizationName": "旧組織",
                                    "businessUnitName": "COO",
                                    "isActive": False,
                                },
                                {
                                    "organizationId": "ORG1",
                                    "organizationName": "システム開発部",
                                    "businessUnitName": "CTO",
                                    "isActive": True,
                                },
                            ]
                        }
                    ]
                ),
                "PositionMaster": FakeTable(),
            }
        )
        app.boto3 = fake_boto3

        response = app.handler({"resource": "/organizations"}, None)
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            [item["organizationId"] for item in body["organizations"]], ["ORG1", "ORG2"]
        )

    def test_get_positions_queries_by_organization_id_gsi(self):
        position_table = FakeTable(
            query_pages=[
                {
                    "Items": [
                        {
                            "positionId": "POS2",
                            "organizationId": "ORG1",
                            "positionName": "エキスパート",
                            "isActive": True,
                        },
                        {
                            "positionId": "POS1",
                            "organizationId": "ORG1",
                            "positionName": "スペシャリスト",
                            "isActive": True,
                        },
                        {
                            "positionId": "OLD",
                            "organizationId": "ORG1",
                            "positionName": "旧",
                            "isActive": False,
                        },
                    ]
                }
            ]
        )
        app.boto3 = FakeBoto3(
            {"OrganizationMaster": FakeTable(), "PositionMaster": position_table}
        )

        response = app.handler(
            {
                "resource": "/positions",
                "queryStringParameters": {"organizationId": "ORG1"},
            },
            None,
        )
        body = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(position_table.scan_calls, 0)
        self.assertEqual(
            position_table.query_kwargs[0]["IndexName"], "organizationId-index"
        )
        self.assertEqual(
            [item["positionId"] for item in body["positions"]], ["POS2", "POS1"]
        )

    def test_get_positions_requires_organization_id(self):
        app.boto3 = FakeBoto3(
            {"OrganizationMaster": FakeTable(), "PositionMaster": FakeTable()}
        )

        response = app.handler(
            {"resource": "/positions", "queryStringParameters": {}}, None
        )

        self.assertEqual(response["statusCode"], 400)


class FakeTable:
    def __init__(self, scan_pages=None, query_pages=None):
        self.scan_pages = list(scan_pages or [])
        self.query_pages = list(query_pages or [])
        self.scan_calls = 0
        self.query_calls = 0
        self.query_kwargs = []

    def scan(self, **_kwargs):
        self.scan_calls += 1
        return self.scan_pages.pop(0)

    def query(self, **kwargs):
        self.query_calls += 1
        self.query_kwargs.append(kwargs)
        return self.query_pages.pop(0)


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
