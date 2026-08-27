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

# UI要件に合わせ、類似度ランキングは上位9件だけ返す。
MAX_RESULT_COUNT = 9
MAX_CHART_SKILL_COUNT = 10


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """API Gatewayから呼ばれるLambdaエントリポイント。

    選択されたpositionIdを受け取り、PositionSkillの全件データから
    他ポジションとのJaccard類似度ランキングを都度計算する。
    """
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

        # PoC段階では事前集計せず、リクエスト時に必要なマスタ/スキル情報を読み込む。
        position_skill_items = _scan_table(dynamodb.Table(position_skill_table_name))
        position_master_items = _scan_table(dynamodb.Table(position_master_table_name))
        skills_by_position = _group_position_skills(position_skill_items)
        position_names = _position_names(position_master_items)

        selected_skills = skills_by_position.get(selected_position_id)
        if not selected_skills:
            # 選択ポジションの評価済みスキルがない場合は、業務上の正常系として空結果を返す。
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

        # 選択ポジションの中核スキル集合を基準に、他ポジションをランキングする。
        selected_core_skills = _core_skill_keys(selected_skills)
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
    """DynamoDBテーブルをページネーション込みで全件Scanする。

    類似度計算は全ポジション比較が必要なため、PoCでは全件取得する。
    """
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
    """PositionSkillの行をpositionId単位にまとめる。

    levelが0〜5の整数ではない行は、類似度計算の軸を壊すため除外する。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        position_id = _normalize_id(item.get("positionId"))
        skill_id = _normalize_id(item.get("skillId"))
        skill_name = _normalize_text(item.get("skillName"))
        organization_name = _normalize_text(item.get("organizationName"))
        business_unit_name = _normalize_text(item.get("businessUnitName"))
        level = _parse_level(item.get("level"))
        if not position_id or not skill_id or not skill_name or level is None:
            logger.warning(
                "Invalid PositionSkill item excluded from similarity: positionId=%s skillId=%s",
                position_id,
                skill_id,
            )
            continue
        grouped.setdefault(position_id, []).append(
            {
                "skillId": skill_id,
                "skillName": skill_name,
                "organizationName": organization_name,
                "businessUnitName": business_unit_name,
                "level": level,
            }
        )
    for skills in grouped.values():
        # 将来ベクトル化するときにも同じ軸順になるよう、skillId順で安定化する。
        skills.sort(key=lambda skill: skill["skillId"])
    return grouped


def _position_names(items: list[dict[str, Any]]) -> dict[str, str]:
    """PositionMasterからpositionIdと表示名の対応表を作る。"""
    names: dict[str, str] = {}
    for item in items:
        position_id = _normalize_id(item.get("positionId"))
        position_name = _normalize_text(item.get("positionName"))
        if position_id and position_name:
            names[position_id] = position_name
    return names


def _core_skill_keys(skills: list[dict[str, Any]]) -> set[tuple[str, int]]:
    """平均+標準偏差以上の(skillId, level)を中核スキルとして扱う。"""
    levels = [skill["level"] for skill in skills]
    if not levels:
        return set()
    mean = sum(levels) / len(levels)
    variance = sum((level - mean) ** 2 for level in levels) / len(levels)
    threshold = mean + math.sqrt(variance)
    return {
        (skill["skillId"], skill["level"])
        for skill in skills
        if skill["level"] >= threshold
    }


def _chart_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """類似ポジションカードの小型レーダーチャートに出す代表スキルを選ぶ。"""
    sorted_skills = sorted(
        skills, key=lambda skill: (-skill["level"], skill["skillName"])
    )
    return [
        {
            "skillId": skill["skillId"],
            "skillName": skill["skillName"],
            "level": skill["level"],
        }
        for skill in sorted_skills[:MAX_CHART_SKILL_COUNT]
    ]


def _jaccard_similarity(
    left: set[tuple[str, int]], right: set[tuple[str, int]]
) -> float:
    """2つの中核スキル集合からJaccard係数を計算する。"""
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _rank_similar_positions(
    selected_position_id: str,
    selected_core_skills: set[tuple[str, int]],
    skills_by_position: dict[str, list[dict[str, Any]]],
    position_names: dict[str, str],
) -> list[dict[str, Any]]:
    """選択ポジション以外を類似度順に並べ、rank付きで上位件数だけ返す。"""
    scored_results: list[dict[str, Any]] = []
    for position_id, skills in skills_by_position.items():
        if position_id == selected_position_id:
            continue
        first_skill = skills[0]
        score = _jaccard_similarity(selected_core_skills, _core_skill_keys(skills))
        scored_results.append(
            {
                "positionId": position_id,
                "positionName": position_names.get(position_id, ""),
                "organizationName": first_skill.get("organizationName", ""),
                "businessUnitName": first_skill.get("businessUnitName", ""),
                "similarityScore": round(score, 4),
                "chartSkills": _chart_skills(skills),
            }
        )

    # 同点時も毎回同じ順序になるよう、表示名とpositionIdでタイブレークする。
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
    """DynamoDB由来のlevelを0〜5の整数として検証・正規化する。"""
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
    """ID項目を比較用に文字列化し、前後空白だけ取り除く。"""
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    """表示テキストを文字列化し、前後空白だけ取り除く。"""
    if value is None:
        return ""
    return str(value).strip()


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """API Gateway Lambda Proxy形式のJSONレスポンスを作る。"""
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
