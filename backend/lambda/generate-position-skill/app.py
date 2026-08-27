import csv
import json
import logging
import os
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CANDIDATE_RULES_PATH = Path(__file__).resolve().parent / "candidate_rules.md"
LEVEL_RULES_PATH = Path(__file__).resolve().parent / "level_rules.md"

CANDIDATE_CONTEXT_TEMPLATE = """{rules}"""

CANDIDATE_DYNAMIC_TEMPLATE = """以下の入力から候補スキルを抽出してください。
{payload}
"""

LEVEL_CONTEXT_TEMPLATE = """{rules}"""

LEVEL_DYNAMIC_TEMPLATE = """以下の入力から候補スキルのレベルを判定してください。
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

    if (
        not model_id
        or not bucket_name
        or not skill_master_table_name
        or not position_skill_table_name
    ):
        logger.error("Missing required environment variables")
        return _error_response(500, "Required environment variables are missing")

    try:
        source_bucket, source_key = _resolve_s3_source(event, bucket_name)
        if not source_key.startswith(POSITION_INPUT_PREFIX):
            raise ValueError("Input CSV must be under position-input/")

        csv_bytes = _download_csv_from_s3(source_bucket, source_key)
        positions = _load_positions_from_csv(csv_bytes)
        if not positions:
            return _error_response(400, "No valid positions found in CSV")

        skill_master = _load_skill_master(skill_master_table_name)
        if not skill_master:
            return _error_response(400, "SkillMaster is empty")

        candidate_rules = _load_candidate_rules()
        level_rules = _load_level_rules()

        total_saved_count = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for position in positions:
            candidate_result = _extract_candidate_skills(
                model_id, candidate_rules, position, skill_master
            )
            candidates = _validate_candidate_skills(
                candidate_result["candidate_skills"], skill_master
            )

            if candidates:
                level_result = _evaluate_skill_levels(
                    model_id, level_rules, position, candidates
                )
                skill_levels = _validate_skill_levels(
                    position["positionId"], level_result["skill_levels"], candidates
                )
            else:
                level_result = _empty_bedrock_result({"skill_levels": []})
                skill_levels = []

            saved_count = _save_position_skill_levels(
                position_skill_table_name,
                source_bucket,
                source_key,
                position,
                skill_levels,
            )
            total_saved_count += saved_count

            candidate_usage = candidate_result["usage"]
            level_usage = level_result["usage"]
            position_input_tokens = (
                candidate_usage["inputTokens"] + level_usage["inputTokens"]
            )
            position_output_tokens = (
                candidate_usage["outputTokens"] + level_usage["outputTokens"]
            )
            total_input_tokens += position_input_tokens
            total_output_tokens += position_output_tokens

            logger.info(
                "Position skill evaluation usage: positionId=%s "
                "candidate_input_tokens=%s candidate_output_tokens=%s "
                "candidate_cache_creation_input_tokens=%s "
                "candidate_cache_read_input_tokens=%s candidate_stop_reason=%s "
                "level_input_tokens=%s level_output_tokens=%s "
                "level_cache_creation_input_tokens=%s level_cache_read_input_tokens=%s "
                "level_stop_reason=%s candidate_count=%s evaluated_count=%s "
                "totalInputTokens=%s totalOutputTokens=%s totalTokens=%s",
                position["positionId"],
                candidate_usage["inputTokens"],
                candidate_usage["outputTokens"],
                candidate_usage["cacheCreationInputTokens"],
                candidate_usage["cacheReadInputTokens"],
                candidate_result["stopReason"],
                level_usage["inputTokens"],
                level_usage["outputTokens"],
                level_usage["cacheCreationInputTokens"],
                level_usage["cacheReadInputTokens"],
                level_result["stopReason"],
                len(candidates),
                len(skill_levels),
                position_input_tokens,
                position_output_tokens,
                position_input_tokens + position_output_tokens,
            )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Position skill levels evaluated successfully",
                    "position_count": len(positions),
                    "saved_count": total_saved_count,
                    "source": {"bucket": source_bucket, "key": source_key},
                    "usage": {
                        "totalInputTokens": total_input_tokens,
                        "totalOutputTokens": total_output_tokens,
                        "totalTokens": total_input_tokens + total_output_tokens,
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


def _load_candidate_rules(path: Path = CANDIDATE_RULES_PATH) -> str:
    return _load_text_file(path, "candidate_rules.md")


def _load_level_rules(path: Path = LEVEL_RULES_PATH) -> str:
    return _load_text_file(path, "level_rules.md")


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
        position = {
            "positionId": position_id,
            "positionName": _normalize_cell(row.get("ポジション名")),
            "businessUnitName": _normalize_cell(row.get("CXO・BU名")),
            "organizationName": _normalize_cell(row.get("組織名")),
            "duties": duties,
            "requiredSkills": required_skills,
        }
        if position["positionName"] or duties or required_skills:
            positions.append(position)

    logger.info("Loaded positions from CSV: %s", len(positions))
    return positions


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

    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            skill_id = _normalize_cell(item.get("skillId"))
            skill_name = _normalize_cell(item.get("skillName"))
            if skill_id and skill_name:
                items.append({"skillId": skill_id, "skillName": skill_name})
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    logger.info("Loaded skill master count: %s", len(items))
    return items


def _extract_candidate_skills(
    model_id: str,
    rules: str,
    position: dict[str, Any],
    skill_master: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "position": position,
        "skill_master": [skill["skillName"] for skill in skill_master],
    }
    content = _build_bedrock_content(
        CANDIDATE_CONTEXT_TEMPLATE.format(rules=rules),
        CANDIDATE_DYNAMIC_TEMPLATE.format(
            payload=json.dumps(payload, ensure_ascii=False)
        ),
    )
    return _invoke_bedrock(model_id, content, _parse_candidate_skills_json)


def _validate_candidate_skills(
    candidate_skill_names: list[str], skill_master: list[dict[str, str]]
) -> list[dict[str, str]]:
    skill_by_name = {skill["skillName"]: skill for skill in skill_master}
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    for value in candidate_skill_names:
        skill_name = _normalize_cell(value)
        if not skill_name or skill_name in seen:
            continue
        skill = skill_by_name.get(skill_name)
        if skill is None:
            continue
        seen.add(skill_name)
        candidates.append(skill)

    return candidates


def _evaluate_skill_levels(
    model_id: str,
    rules: str,
    position: dict[str, Any],
    candidate_skills: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "position": position,
        "candidate_skills": [skill["skillName"] for skill in candidate_skills],
    }
    content = _build_bedrock_content(
        LEVEL_CONTEXT_TEMPLATE.format(rules=rules),
        LEVEL_DYNAMIC_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False)),
    )
    return _invoke_bedrock(model_id, content, _parse_skill_levels_json)


def _validate_skill_levels(
    position_id: str,
    skill_levels: list[dict[str, Any]],
    candidate_skills: list[dict[str, str]],
) -> list[dict[str, Any]]:
    skill_by_name = {skill["skillName"]: skill for skill in candidate_skills}
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in skill_levels:
        skill_name = _normalize_cell(item.get("skill_name"))
        if not skill_name or skill_name in seen:
            continue
        skill = skill_by_name.get(skill_name)
        if skill is None:
            continue
        level = item.get("level")
        if (
            isinstance(level, bool)
            or not isinstance(level, int)
            or level < 0
            or level > 5
        ):
            raise ValueError(f"Invalid level for position {position_id}: {skill_name}")
        seen.add(skill_name)
        validated.append({**skill, "level": level})

    return validated


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
                    "positionName": position["positionName"],
                    "businessUnitName": position["businessUnitName"],
                    "organizationName": position["organizationName"],
                    "skillName": skill_level["skillName"],
                    "level": skill_level["level"],
                    "sourceBucket": source_bucket,
                    "sourceKey": source_key,
                    "evaluatedAt": evaluated_at,
                }
            )
            count += 1

    return count


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
        "max_tokens": 3000,
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


def _empty_bedrock_result(data: dict[str, Any]) -> dict[str, Any]:
    return {
        **data,
        "usage": {
            "inputTokens": 0,
            "outputTokens": 0,
            "totalTokens": 0,
            "cacheCreationInputTokens": 0,
            "cacheReadInputTokens": 0,
        },
        "stopReason": "",
    }


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


def _parse_candidate_skills_json(text: str) -> dict[str, Any]:
    data = _extract_json_object(text)
    candidate_skills = data.get("candidate_skills") if isinstance(data, dict) else None
    if not isinstance(candidate_skills, list):
        raise ValueError("Bedrock output must contain candidate_skills array")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in candidate_skills:
        if not isinstance(item, str):
            raise ValueError("candidate_skills entries must be strings")
        skill_name = _normalize_cell(item)
        if skill_name and skill_name not in seen:
            seen.add(skill_name)
            normalized.append(skill_name)
    return {"candidate_skills": normalized}


def _parse_skill_levels_json(text: str) -> dict[str, Any]:
    data = _extract_json_object(text)
    skill_levels = data.get("skill_levels") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(skill_levels, list):
        raise ValueError("Bedrock output must contain skill_levels array")

    parsed_levels: list[dict[str, Any]] = []
    for item in skill_levels:
        if not isinstance(item, dict):
            raise ValueError("skill_levels entries must be objects")
        skill_name = _normalize_cell(item.get("skill_name"))
        level = item.get("level")
        if not skill_name:
            continue
        parsed_levels.append({"skill_name": skill_name, "level": level})
    return {"skill_levels": parsed_levels}


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
