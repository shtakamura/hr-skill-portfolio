import csv
import json
import logging
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

LEVEL_RULES_PATH = Path(__file__).resolve().parent / "level_rules.md"
DEFAULT_POSITION_SKILL_BATCH_SIZE = 50
BEDROCK_MAX_TOKENS = 1000

LEVEL_CONTEXT_TEMPLATE = """{rules}"""

LEVEL_DYNAMIC_TEMPLATE = """以下の入力から、skills配列とまったく同じ順番でlevels配列を返してください。

重要:
- skills配列を並べ替えない
- スキルを追加しない
- スキルを削除しない
- スキルを統合しない
- 各入力スキルに対し、0〜5の整数レベルを必ず1件返す
- n件のskillsを受け取った場合、n件のlevelsを返す
- 出力はJSONオブジェクト {{"levels":[...]}} のみとする
- skillId、skillName、positionId、追加の説明項目を出力しない

{payload}
"""

POSITION_INPUT_PREFIX = "position-input/"


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """ポジションCSVを読み込み、候補抽出とレベル判定を順番に実行する。"""
    logger.info("Received event")

    model_id = os.environ.get("BEDROCK_MODEL_ID")
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    skill_master_table_name = os.environ.get("SKILL_MASTER_TABLE_NAME")
    position_skill_table_name = os.environ.get("POSITION_SKILL_TABLE_NAME")
    organization_master_table_name = os.environ.get("ORGANIZATION_MASTER_TABLE_NAME")
    position_master_table_name = os.environ.get("POSITION_MASTER_TABLE_NAME")
    batch_size_text = os.environ.get("POSITION_SKILL_BATCH_SIZE")

    if (
        not model_id
        or not bucket_name
        or not skill_master_table_name
        or not position_skill_table_name
        or not organization_master_table_name
        or not position_master_table_name
    ):
        logger.error("Missing required environment variables")
        return _error_response(500, "Required environment variables are missing")

    try:
        batch_size = _load_batch_size(batch_size_text)
        source_bucket, source_key = _resolve_s3_source(event, bucket_name)
        if not source_key.startswith(POSITION_INPUT_PREFIX):
            raise ValueError("Input CSV must be under position-input/")

        csv_bytes = _download_csv_from_s3(source_bucket, source_key)
        positions = _load_positions_from_csv(csv_bytes)
        if not positions:
            return _error_response(400, "No valid positions found in CSV")

        master_saved_counts = _save_position_masters(
            organization_master_table_name,
            position_master_table_name,
            positions,
        )

        skill_master = _sort_skill_master(_load_skill_master(skill_master_table_name))
        level_rules = _load_level_rules()
        skill_batches = _split_skill_batches(skill_master, batch_size)

        total_evaluated_count = 0
        total_usage = _empty_usage()

        for position in positions:
            evaluation = _evaluate_all_skill_levels(
                model_id, level_rules, position, skill_batches
            )
            skill_levels = evaluation["skillLevels"]
            _validate_complete_skill_levels(skill_master, skill_levels)

            saved_count = _save_position_skill_levels(
                position_skill_table_name,
                source_bucket,
                source_key,
                position,
                skill_levels,
            )
            _delete_stale_position_skill_levels(
                position_skill_table_name, position["positionId"], skill_master
            )
            total_evaluated_count += saved_count
            _add_usage(total_usage, evaluation["usage"])

            logger.info(
                "Position skill level usage: positionId=%s skillMasterCount=%s "
                "batchCount=%s evaluatedCount=%s inputTokens=%s outputTokens=%s "
                "totalTokens=%s cacheCreationInputTokens=%s cacheReadInputTokens=%s "
                "stopReasons=%s",
                position["positionId"],
                len(skill_master),
                evaluation["usage"]["batchCount"],
                len(skill_levels),
                evaluation["usage"]["inputTokens"],
                evaluation["usage"]["outputTokens"],
                evaluation["usage"]["totalTokens"],
                evaluation["usage"]["cacheCreationInputTokens"],
                evaluation["usage"]["cacheReadInputTokens"],
                ",".join(evaluation["stopReasons"]),
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Position skill levels evaluated and saved successfully",
                    "positionCount": len(positions),
                    "skillMasterCount": len(skill_master),
                    "evaluatedCount": total_evaluated_count,
                    "organization_saved_count": master_saved_counts[
                        "organizationSavedCount"
                    ],
                    "position_saved_count": master_saved_counts["positionSavedCount"],
                    "usage": {
                        "inputTokens": total_usage["inputTokens"],
                        "outputTokens": total_usage["outputTokens"],
                        "totalTokens": total_usage["totalTokens"],
                        "cacheCreationInputTokens": total_usage[
                            "cacheCreationInputTokens"
                        ],
                        "cacheReadInputTokens": total_usage["cacheReadInputTokens"],
                    },
                },
                ensure_ascii=False,
            ),
        }
    except ValueError as err:
        logger.exception("Validation error")
        return _error_response(400, str(err))
    except (ClientError, BotoCoreError) as err:
        logger.exception("AWS client error")
        return _error_response(502, f"AWS service error: {str(err)}")
    except Exception as err:  # pylint: disable=broad-exception-caught
        logger.exception("Unexpected error")
        return _error_response(500, f"Unexpected error: {str(err)}")


def _load_level_rules(path: Path = LEVEL_RULES_PATH) -> str:
    return _load_text_file(path, "level_rules.md")


def _load_batch_size(value: str | None) -> int:
    if value is None or not value.strip():
        return DEFAULT_POSITION_SKILL_BATCH_SIZE
    try:
        batch_size = int(value)
    except ValueError as err:
        raise ValueError(
            "POSITION_SKILL_BATCH_SIZE must be a positive integer"
        ) from err
    if batch_size < 1:
        raise ValueError("POSITION_SKILL_BATCH_SIZE must be a positive integer")
    return batch_size


def _load_text_file(path: Path, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        raise ValueError(f"Unable to read {label}") from err

    content = content.strip()
    if not content:
        raise ValueError(f"{label} is empty")
    return content


def _resolve_s3_source(event: dict[str, Any], default_bucket: str) -> tuple[str, str]:
    records = event.get("Records")
    if isinstance(records, list) and records:
        s3_info = records[0].get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name") or default_bucket
        raw_key = s3_info.get("object", {}).get("key")
        if not raw_key:
            raise ValueError("S3 event does not contain object key")
        return bucket, unquote_plus(raw_key)

    key = event.get("key") or event.get("s3_key")
    bucket = event.get("bucket") or event.get("s3_bucket") or default_bucket
    if not key:
        raise ValueError("Input event must contain S3 key")
    return bucket, key


def _download_csv_from_s3(bucket: str, key: str) -> bytes:
    logger.info("Downloading CSV from S3: s3://%s/%s", bucket, key)
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _load_positions_from_csv(csv_bytes: bytes) -> list[dict[str, Any]]:
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")

    required_columns = [
        "ポジションコード",
        "ポジション名",
        "CXO・BU名",
        "組織名",
        "主な職務#1",
        "主な職務#1 関与度(%)",
        "主な職務#2",
        "主な職務#2 関与度(%)",
        "主な職務#3",
        "主な職務#3 関与度(%)",
        "主な職務#4",
        "主な職務#4 関与度(%)",
        "主な職務#5",
        "主な職務#5 関与度(%)",
        "必要知識・スキル(知識・スキル)",
    ]
    missing_columns = [
        column for column in required_columns if column not in reader.fieldnames
    ]
    if missing_columns:
        raise ValueError(
            f"CSV required columns are missing: {', '.join(missing_columns)}"
        )

    positions: list[dict[str, Any]] = []
    seen_position_ids: set[str] = set()
    for row in reader:
        position_id = _normalize_cell(row.get("ポジションコード"))
        if not position_id:
            continue
        if position_id in seen_position_ids:
            raise ValueError(f"Duplicate position code found: {position_id}")
        seen_position_ids.add(position_id)

        duties = []
        for duty_index in range(1, 6):
            duty = _normalize_cell(row.get(f"主な職務#{duty_index}"))
            weight = _parse_weight(row.get(f"主な職務#{duty_index} 関与度(%)"))
            if duty:
                duties.append({"name": duty, "weight": weight})

        required_skills = _split_required_skills(
            row.get("必要知識・スキル(知識・スキル)")
        )
        organization_name = _normalize_cell(row.get("組織名"))
        business_unit_name = _normalize_cell(row.get("CXO・BU名"))
        position = {
            "positionId": position_id,
            "positionName": _strip_organization_suffix(
                _normalize_cell(row.get("ポジション名")),
                organization_name,
            ),
            "businessUnitName": business_unit_name,
            "organizationName": organization_name,
            "duties": duties,
            "requiredSkills": required_skills,
        }
        position["organizationId"] = _build_organization_id(
            position["organizationName"], position["businessUnitName"]
        )
        if position["positionName"] or duties or required_skills:
            positions.append(position)

    logger.info("Loaded positions from CSV: %s", len(positions))
    return positions


def _strip_organization_suffix(position_name: str, organization_name: str) -> str:
    if not position_name or not organization_name:
        return position_name
    suffixes = (f"（{organization_name}）", f"({organization_name})")
    for suffix in suffixes:
        if position_name.endswith(suffix):
            return position_name[: -len(suffix)].strip()
    return position_name


def _build_organization_id(organization_name: str, business_unit_name: str) -> str:
    source = f"{_normalize_identity(organization_name)}\n{_normalize_identity(business_unit_name)}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, source))


def _normalize_identity(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _normalize_cell(value))
    return re.sub(r"\s+", " ", text)


def _save_position_masters(
    organization_table_name: str,
    position_table_name: str,
    positions: list[dict[str, Any]],
) -> dict[str, int]:
    dynamodb = boto3.resource("dynamodb")
    organization_table = dynamodb.Table(organization_table_name)
    position_table = dynamodb.Table(position_table_name)
    now = datetime.now(timezone.utc).isoformat()

    organization_items: dict[str, dict[str, Any]] = {}
    for position in positions:
        organization_id = position["organizationId"]
        organization_items[organization_id] = {
            "organizationId": organization_id,
            "organizationName": position["organizationName"],
            "businessUnitName": position["businessUnitName"],
            "isActive": True,
            "updatedAt": now,
        }

    with organization_table.batch_writer() as batch:
        for item in organization_items.values():
            batch.put_item(Item=item)

    with position_table.batch_writer() as batch:
        for position in positions:
            batch.put_item(
                Item={
                    "positionId": position["positionId"],
                    "organizationId": position["organizationId"],
                    "positionName": position["positionName"],
                    "isActive": True,
                    "updatedAt": now,
                }
            )

    logger.info(
        "Saved position masters: organization_count=%s position_count=%s",
        len(organization_items),
        len(positions),
    )
    return {
        "organizationSavedCount": len(organization_items),
        "positionSavedCount": len(positions),
    }


def _parse_weight(value: Any) -> int | None:
    text = _normalize_cell(value)
    if not text:
        return None
    text = text.rstrip("%")
    try:
        weight = int(float(text))
    except ValueError:
        return None
    if weight < 0:
        return None
    return weight


def _split_required_skills(value: Any) -> list[str]:
    text = _normalize_cell(value)
    if not text:
        return []
    skills: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[、,;；\n]+", text):
        skill = _normalize_cell(part)
        if skill and skill not in seen:
            seen.add(skill)
            skills.append(skill)
    return skills


def _load_skill_master(table_name: str) -> list[dict[str, str]]:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    items: list[dict[str, str]] = []
    scan_kwargs: dict[str, Any] = {}
    seen_skill_ids: set[str] = set()

    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            skill_id = _normalize_cell(item.get("skillId"))
            skill_name = _normalize_cell(item.get("skillName"))
            category = _normalize_cell(item.get("category"))
            subcategory = _normalize_cell(item.get("subcategory"))
            if not skill_id or not skill_name:
                continue
            if skill_id in seen_skill_ids:
                raise ValueError(f"Duplicate skillId found in SkillMaster: {skill_id}")
            seen_skill_ids.add(skill_id)
            items.append(
                {
                    "skillId": skill_id,
                    "skillName": skill_name,
                    "category": category,
                    "subcategory": subcategory,
                }
            )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    if not items:
        raise ValueError("SkillMaster is empty")

    logger.info("Loaded skill master count: %s", len(items))
    return items


def _sort_skill_master(skill_master: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(skill_master, key=lambda skill: skill["skillId"])


def _split_skill_batches(
    skill_master: list[dict[str, str]], batch_size: int
) -> list[list[dict[str, str]]]:
    return [
        skill_master[index : index + batch_size]
        for index in range(0, len(skill_master), batch_size)
    ]


def _evaluate_all_skill_levels(
    model_id: str,
    rules: str,
    position: dict[str, Any],
    skill_batches: list[list[dict[str, str]]],
) -> dict[str, Any]:
    all_skill_levels: list[dict[str, Any]] = []
    usage = _empty_usage()
    stop_reasons: list[str] = []

    for batch_index, skill_batch in enumerate(skill_batches, start=1):
        result = _evaluate_skill_batch(model_id, rules, position, skill_batch)
        all_skill_levels.extend(result["skillLevels"])
        _add_usage(usage, result["usage"])
        usage["batchCount"] += 1
        stop_reasons.append(result["stopReason"])
        logger.info(
            "Position skill level batch usage: positionId=%s batchNumber=%s "
            "batchSize=%s inputTokens=%s outputTokens=%s "
            "cacheCreationInputTokens=%s cacheReadInputTokens=%s stopReason=%s",
            position["positionId"],
            batch_index,
            len(skill_batch),
            result["usage"]["inputTokens"],
            result["usage"]["outputTokens"],
            result["usage"]["cacheCreationInputTokens"],
            result["usage"]["cacheReadInputTokens"],
            result["stopReason"],
        )

    usage["evaluatedCount"] = len(all_skill_levels)
    return {
        "skillLevels": all_skill_levels,
        "usage": usage,
        "stopReasons": stop_reasons,
    }


def _evaluate_skill_batch(
    model_id: str,
    rules: str,
    position: dict[str, Any],
    skill_batch: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "position": position,
        "skills": [skill["skillName"] for skill in skill_batch],
    }
    content = _build_bedrock_content(
        LEVEL_CONTEXT_TEMPLATE.format(rules=rules),
        LEVEL_DYNAMIC_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False)),
    )
    result = _invoke_bedrock(
        model_id,
        content,
        lambda text: _parse_levels_json(text, expected_count=len(skill_batch)),
    )
    return {
        "skillLevels": _restore_skill_levels(skill_batch, result["levels"]),
        "usage": result["usage"],
        "stopReason": result["stopReason"],
    }


def _restore_skill_levels(
    skill_batch: list[dict[str, str]], levels: list[int]
) -> list[dict[str, Any]]:
    if len(skill_batch) != len(levels):
        raise ValueError("levels count must match skill batch count before restore")
    return [
        {
            "skillId": skill["skillId"],
            "skillName": skill["skillName"],
            "category": skill.get("category", ""),
            "subcategory": skill.get("subcategory", ""),
            "level": level,
        }
        for skill, level in zip(skill_batch, levels)
    ]


def _merge_batch_results(
    batch_results: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for batch_result in batch_results:
        merged.extend(batch_result)
    return merged


def _validate_complete_skill_levels(
    skill_master: list[dict[str, str]], skill_levels: list[dict[str, Any]]
) -> None:
    expected_skill_ids = [skill["skillId"] for skill in skill_master]
    actual_skill_ids = [skill["skillId"] for skill in skill_levels]
    if len(actual_skill_ids) != len(expected_skill_ids):
        raise ValueError("Evaluated skill count must match SkillMaster count")
    if len(actual_skill_ids) != len(set(actual_skill_ids)):
        raise ValueError("Evaluated skill levels contain duplicate skillId")
    if actual_skill_ids != expected_skill_ids:
        raise ValueError("Evaluated skillIds must match SkillMaster skillIds in order")
    for skill_level in skill_levels:
        level = skill_level.get("level")
        if (
            isinstance(level, bool)
            or not isinstance(level, int)
            or level < 0
            or level > 5
        ):
            raise ValueError(
                "Evaluated skill levels must contain only integers from 0 to 5"
            )


def _save_position_skill_levels(
    table_name: str,
    source_bucket: str,
    source_key: str,
    position: dict[str, Any],
    skill_levels: list[dict[str, Any]],
) -> int:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    evaluated_at = datetime.now(timezone.utc).isoformat()
    count = 0

    with table.batch_writer() as batch:
        for skill_level in skill_levels:
            batch.put_item(
                Item={
                    "positionId": position["positionId"],
                    "skillId": skill_level["skillId"],
                    "organizationId": position["organizationId"],
                    "positionName": position["positionName"],
                    "businessUnitName": position["businessUnitName"],
                    "organizationName": position["organizationName"],
                    "skillName": skill_level["skillName"],
                    "category": skill_level.get("category", ""),
                    "subcategory": skill_level.get("subcategory", ""),
                    "level": skill_level["level"],
                    "sourceBucket": source_bucket,
                    "sourceKey": source_key,
                    "evaluatedAt": evaluated_at,
                }
            )
            count += 1

    return count


def _delete_stale_position_skill_levels(
    table_name: str, position_id: str, skill_master: list[dict[str, str]]
) -> int:
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    valid_skill_ids = {skill["skillId"] for skill in skill_master}
    stale_items: list[dict[str, str]] = []
    query_kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key("positionId").eq(position_id)
    }

    while True:
        response = table.query(**query_kwargs)
        for item in response.get("Items", []):
            skill_id = _normalize_cell(item.get("skillId"))
            if skill_id and skill_id not in valid_skill_ids:
                stale_items.append({"positionId": position_id, "skillId": skill_id})
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_kwargs["ExclusiveStartKey"] = last_key

    if not stale_items:
        return 0

    with table.batch_writer() as batch:
        for key in stale_items:
            batch.delete_item(Key=key)

    logger.info(
        "Deleted stale PositionSkill items: positionId=%s deletedCount=%s",
        position_id,
        len(stale_items),
    )
    return len(stale_items)


def _build_bedrock_content(rules: str, dynamic_payload: str) -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": rules,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": dynamic_payload},
    ]


def _invoke_bedrock(
    model_id: str,
    content: list[dict[str, Any]],
    parser,
) -> dict[str, Any]:
    logger.info("Invoking Bedrock model: %s", model_id)
    bedrock = boto3.client("bedrock-runtime")
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": BEDROCK_MAX_TOKENS,
        "messages": [{"role": "user", "content": content}],
    }
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body, ensure_ascii=False),
        contentType="application/json",
        accept="application/json",
    )

    payload = json.loads(response["body"].read())
    usage = _extract_bedrock_usage(payload)
    stop_reason = _extract_bedrock_stop_reason(payload)
    if stop_reason == "max_tokens":
        raise ValueError("Bedrock output was truncated because max_tokens was reached")

    generated_text = _extract_bedrock_text(payload)
    try:
        parsed = parser(generated_text)
    except json.JSONDecodeError:
        _log_bedrock_json_parse_failure(generated_text, payload)
        raise

    parsed["usage"] = usage
    parsed["stopReason"] = stop_reason
    return parsed


def _empty_usage() -> dict[str, int]:
    return {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "cacheCreationInputTokens": 0,
        "cacheReadInputTokens": 0,
        "batchCount": 0,
        "evaluatedCount": 0,
    }


def _add_usage(total: dict[str, int], usage: dict[str, int]) -> None:
    total["inputTokens"] += usage["inputTokens"]
    total["outputTokens"] += usage["outputTokens"]
    total["totalTokens"] = total["inputTokens"] + total["outputTokens"]
    total["cacheCreationInputTokens"] += usage["cacheCreationInputTokens"]
    total["cacheReadInputTokens"] += usage["cacheReadInputTokens"]


def _extract_bedrock_usage(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "cacheCreationInputTokens": 0,
            "cacheReadInputTokens": 0,
        }

    input_tokens = _safe_token_count(usage.get("input_tokens"))
    output_tokens = _safe_token_count(usage.get("output_tokens"))
    cache_creation_input_tokens = _safe_token_count(
        usage.get("cache_creation_input_tokens")
    )
    cache_read_input_tokens = _safe_token_count(usage.get("cache_read_input_tokens"))
    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens,
        "cacheCreationInputTokens": cache_creation_input_tokens,
        "cacheReadInputTokens": cache_read_input_tokens,
    }


def _safe_token_count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _extract_bedrock_stop_reason(payload: dict[str, Any]) -> str:
    stop_reason = payload.get("stop_reason")
    if isinstance(stop_reason, str):
        return stop_reason
    return ""


def _extract_bedrock_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        text_blocks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                text_blocks.append(text.strip())
        if text_blocks:
            return "\n".join(text_blocks)

    raise ValueError("Unable to extract text from Bedrock response")


def _parse_levels_json(text: str, expected_count: int) -> dict[str, Any]:
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        raise ValueError("Bedrock output must be a JSON object")
    if set(data.keys()) != {"levels"}:
        raise ValueError("Bedrock output must contain only levels")
    levels = data.get("levels")
    if not isinstance(levels, list):
        raise ValueError("Bedrock output levels must be an array")
    if len(levels) != expected_count:
        raise ValueError("Bedrock output levels count must match skill batch count")

    parsed_levels: list[int] = []
    for level in levels:
        if (
            isinstance(level, bool)
            or not isinstance(level, int)
            or level < 0
            or level > 5
        ):
            raise ValueError(
                "Bedrock output levels must contain only integers from 0 to 5"
            )
        parsed_levels.append(level)
    return {"levels": parsed_levels}


def _extract_json_object(text: str) -> Any:
    json_text = text.strip()
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", json_text, re.DOTALL):
        fenced_text = match.group(1).strip()
        try:
            return json.loads(fenced_text)
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    last_error: json.JSONDecodeError | None = None
    for index, char in enumerate(json_text):
        if char != "{":
            continue
        try:
            data, _end = decoder.raw_decode(json_text[index:])
        except json.JSONDecodeError as err:
            last_error = err
            continue
        return data

    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("No JSON object found", json_text, 0)


def _log_bedrock_json_parse_failure(text: str, payload: dict[str, Any]) -> None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        usage = {}
    logger.warning(
        "Failed to parse Bedrock JSON response: text_length=%s stop_reason=%s "
        "input_tokens=%s output_tokens=%s",
        len(text),
        payload.get("stop_reason"),
        usage.get("input_tokens"),
        usage.get("output_tokens"),
    )


def _normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "body": json.dumps({"message": message}, ensure_ascii=False),
    }
