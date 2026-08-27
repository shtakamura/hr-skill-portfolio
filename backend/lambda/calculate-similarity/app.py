import json
import logging
import math
import os
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_RESULT_COUNT = 20


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    position_skill_table_name = os.environ.get("POSITION_SKILL_TABLE_NAME")
    position_master_table_name = os.environ.get("POSITION_MASTER_TABLE_NAME")
    if not position_skill_table_name or not position_master_table_name:
        logger.error("Missing required environment variables")
        return _response(500, {"message": "Required environment variables are missing"})

    params = event.get("queryStringParameters") or {}
    selected_position_id = _normalize_id(params.get("positionId"))
    if not selected_position_id:
        return _response(400, {"message": "positionId is required"})

    try:
        dynamodb = boto3.resource("dynamodb")
        position_skill_items = _scan_table(dynamodb.Table(position_skill_table_name))
        position_master_items = _scan_table(dynamodb.Table(position_master_table_name))
        skills_by_position = _group_position_skills(position_skill_items)
        position_names = _position_names(position_master_items)

        selected_skills = skills_by_position.get(selected_position_id)
        if not selected_skills:
            logger.info(
                "Similarity lookup: selectedPositionId=%s positionCount=%s resultCount=0 dataFound=false",
                selected_position_id,
                len(skills_by_position),
            )
            return _response(
                200,
                {
                    "dataFound": False,
                    "selectedPositionId": selected_position_id,
                    "results": [],
                },
            )

        selected_core_skills = _core_skill_ids(selected_skills)
        results = _rank_similar_positions(
            selected_position_id,
            selected_core_skills,
            skills_by_position,
            position_names,
        )

        logger.info(
            "Similarity lookup: selectedPositionId=%s positionCount=%s selectedCoreSkillCount=%s resultCount=%s dataFound=true",
            selected_position_id,
            len(skills_by_position),
            len(selected_core_skills),
            len(results),
        )
        return _response(
            200,
            {
                "dataFound": True,
                "selectedPositionId": selected_position_id,
                "results": results,
            },
        )
    except (ClientError, BotoCoreError) as err:
        logger.exception("AWS client error")
        return _response(502, {"message": f"AWS service error: {str(err)}"})
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error")
        return _response(500, {"message": f"Unexpected error: {str(err)}"})


def _scan_table(table: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs: dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    return items


def _group_position_skills(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        position_id = _normalize_id(item.get("positionId"))
        skill_id = _normalize_id(item.get("skillId"))
        skill_name = _normalize_text(item.get("skillName"))
        level = _parse_level(item.get("level"))
        if not position_id or not skill_id or not skill_name or level is None:
            logger.warning(
                "Invalid PositionSkill item excluded from similarity: positionId=%s skillId=%s",
                position_id,
                skill_id,
            )
            continue
        grouped.setdefault(position_id, []).append(
            {"skillId": skill_id, "skillName": skill_name, "level": level}
        )
    for skills in grouped.values():
        skills.sort(key=lambda skill: skill["skillId"])
    return grouped


def _position_names(items: list[dict[str, Any]]) -> dict[str, str]:
    names: dict[str, str] = {}
    for item in items:
        position_id = _normalize_id(item.get("positionId"))
        position_name = _normalize_text(item.get("positionName"))
        if position_id and position_name:
            names[position_id] = position_name
    return names


def _core_skill_ids(skills: list[dict[str, Any]]) -> set[str]:
    levels = [skill["level"] for skill in skills]
    if not levels:
        return set()
    mean = sum(levels) / len(levels)
    variance = sum((level - mean) ** 2 for level in levels) / len(levels)
    threshold = mean + math.sqrt(variance)
    return {skill["skillId"] for skill in skills if skill["level"] >= threshold}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _rank_similar_positions(
    selected_position_id: str,
    selected_core_skills: set[str],
    skills_by_position: dict[str, list[dict[str, Any]]],
    position_names: dict[str, str],
) -> list[dict[str, Any]]:
    scored_results: list[dict[str, Any]] = []
    for position_id, skills in skills_by_position.items():
        if position_id == selected_position_id:
            continue
        score = _jaccard_similarity(selected_core_skills, _core_skill_ids(skills))
        scored_results.append(
            {
                "positionId": position_id,
                "positionName": position_names.get(position_id, ""),
                "similarityScore": round(score, 4),
            }
        )

    scored_results.sort(
        key=lambda item: (
            -item["similarityScore"],
            item["positionName"],
            item["positionId"],
        )
    )
    return [
        {"rank": index + 1, **item}
        for index, item in enumerate(scored_results[:MAX_RESULT_COUNT])
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
