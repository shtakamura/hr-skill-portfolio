import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POSITION_ORGANIZATION_INDEX_NAME = "organizationId-index"


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    organization_table_name = os.environ.get("ORGANIZATION_MASTER_TABLE_NAME")
    position_table_name = os.environ.get("POSITION_MASTER_TABLE_NAME")
    if not organization_table_name or not position_table_name:
        logger.error("Missing required master table environment variables")
        return _response(500, {"message": "Required environment variables are missing"})

    try:
        resource = boto3.resource("dynamodb")
        path = event.get("resource") or event.get("path") or ""
        params = event.get("queryStringParameters") or {}

        if path.endswith("/organizations"):
            organizations = _load_organizations(resource.Table(organization_table_name))
            logger.info("Organization lookup: count=%s", len(organizations))
            return _response(200, {"organizations": organizations})

        if path.endswith("/positions"):
            organization_id = _normalize_id(params.get("organizationId"))
            if not organization_id:
                return _response(400, {"message": "organizationId is required"})
            positions = _load_positions(
                resource.Table(position_table_name), organization_id
            )
            logger.info(
                "Position lookup: organizationId=%s count=%s",
                organization_id,
                len(positions),
            )
            return _response(200, {"positions": positions})

        return _response(404, {"message": "Route not found"})
    except (ClientError, BotoCoreError) as err:
        logger.exception("AWS client error")
        return _response(502, {"message": f"AWS service error: {str(err)}"})
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error")
        return _response(500, {"message": f"Unexpected error: {str(err)}"})


def _load_organizations(table: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(
            _organization_from_item(item) for item in response.get("Items", [])
        )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return sorted(
        [item for item in items if item["organizationId"] and item["isActive"]],
        key=lambda item: (
            item["organizationName"],
            item["businessUnitName"],
            item["organizationId"],
        ),
    )


def _load_positions(table: Any, organization_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": POSITION_ORGANIZATION_INDEX_NAME,
        "KeyConditionExpression": Key("organizationId").eq(organization_id),
    }
    while True:
        response = table.query(**query_kwargs)
        items.extend(_position_from_item(item) for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return sorted(
        [item for item in items if item["positionId"] and item["isActive"]],
        key=lambda item: (item["positionName"], item["positionId"]),
    )


def _organization_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "organizationId": _normalize_id(item.get("organizationId")),
        "organizationName": _normalize_text(item.get("organizationName")),
        "businessUnitName": _normalize_text(item.get("businessUnitName")),
        "isActive": _parse_bool(item.get("isActive")),
    }


def _position_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "positionId": _normalize_id(item.get("positionId")),
        "organizationId": _normalize_id(item.get("organizationId")),
        "positionName": _normalize_text(item.get("positionName")),
        "isActive": _parse_bool(item.get("isActive")),
    }


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value == Decimal(1)
    return False


def _normalize_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ALLOW_ORIGIN", ""),
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
