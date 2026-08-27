import json
import logging
import os
import re
import unicodedata
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

POSITION_NAME_INDEX_NAME = "organizationName-positionName-index"
MAX_SKILL_COUNT = 10


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    table_name = os.environ.get("POSITION_SKILL_TABLE_NAME")
    if not table_name:
        logger.error("Missing required environment variable: POSITION_SKILL_TABLE_NAME")
        return _response(500, {"message": "Required environment variables are missing"})

    params = event.get("queryStringParameters") or {}
    position_id = _normalize(params.get("positionId"))
    organization_name = _normalize(params.get("organizationName"))
    position_name = _normalize(params.get("positionName"))

    if not position_id and (not organization_name or not position_name):
        return _response(
            400,
            {
                "message": "positionId or both organizationName and positionName are required"
            },
        )

    try:
        table = boto3.resource("dynamodb").Table(table_name)
        if position_id:
            search_method = "positionId"
            items = _query_by_position_id(table, position_id)
        else:
            search_method = "organizationName+positionName"
            items = _query_by_position_name(table, organization_name, position_name)
            items = _only_unique_position_items(items)

        response_body = _build_response(
            items,
            requested_position_id=position_id or None,
            requested_organization_name=organization_name or None,
            requested_position_name=position_name or None,
        )

        logger.info(
            "Position skills lookup: searchMethod=%s positionId=%s resultCount=%s "
            "validSkillCount=%s topSkillCount=%s dataFound=%s",
            search_method,
            response_body["positionId"],
            len(items),
            response_body["validSkillCount"],
            len(response_body["skills"]),
            response_body["dataFound"],
        )
        return _response(200, response_body)
    except (ClientError, BotoCoreError) as err:
        logger.exception("AWS client error")
        return _response(502, {"message": f"AWS service error: {str(err)}"})
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error")
        return _response(500, {"message": f"Unexpected error: {str(err)}"})


def _query_by_position_id(table: Any, position_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("positionId").eq(position_id)
    }
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return items


def _query_by_position_name(
    table: Any, organization_name: str, position_name: str
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    query_kwargs: dict[str, Any] = {
        "IndexName": POSITION_NAME_INDEX_NAME,
        "KeyConditionExpression": Key("organizationName").eq(organization_name)
        & Key("positionName").eq(position_name),
    }
    while True:
        response = table.query(**query_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key
    return items


def _build_response(
    items: list[dict[str, Any]],
    requested_position_id: str | None,
    requested_organization_name: str | None,
    requested_position_name: str | None,
) -> dict[str, Any]:
    valid_skills = _valid_skill_items(items)
    selected_skills = _top_skills(valid_skills)
    first_item = items[0] if items else {}
    data_found = len(selected_skills) > 0

    return {
        "dataFound": data_found,
        "positionId": (
            first_item.get("positionId") if data_found else requested_position_id
        ),
        "organizationName": (
            first_item.get("organizationName")
            if data_found
            else requested_organization_name
        ),
        "positionName": (
            first_item.get("positionName") if data_found else requested_position_name
        ),
        "skills": selected_skills,
        "validSkillCount": len(valid_skills),
    }


def _only_unique_position_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    position_ids = {
        _normalize(item.get("positionId"))
        for item in items
        if _normalize(item.get("positionId"))
    }
    if len(position_ids) <= 1:
        return items
    logger.warning(
        "Ambiguous PositionSkill name lookup excluded: matchedPositionCount=%s",
        len(position_ids),
    )
    return []


def _valid_skill_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen_skill_ids: set[str] = set()
    for item in items:
        skill_id = _normalize(item.get("skillId"))
        skill_name = _normalize(item.get("skillName"))
        level = _parse_level(item.get("level"))
        if not skill_id or not skill_name or level is None:
            logger.warning(
                "Invalid PositionSkill item excluded: positionId=%s skillId=%s",
                _normalize(item.get("positionId")),
                skill_id or "",
            )
            continue
        if skill_id in seen_skill_ids:
            continue
        seen_skill_ids.add(skill_id)
        skills.append({"skillId": skill_id, "skillName": skill_name, "level": level})
    return skills


def _top_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(skills, key=lambda skill: (-skill["level"], skill["skillName"]))[
        :MAX_SKILL_COUNT
    ]


def _parse_level(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        level = value
    elif isinstance(value, Decimal) and value == value.to_integral_value():
        level = int(value)
    else:
        return None
    if level < 0 or level > 5:
        return None
    return level


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value).strip())
    return re.sub(r"\s+", " ", text)


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
