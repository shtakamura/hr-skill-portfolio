import csv
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from io import StringIO
from typing import Any
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# このLambdaは、CSVの職務情報を集約してBedrockで共通スキルマスタを生成し、
# DynamoDBへ保存する責務を持つ。
PROMPT_TEMPLATE = """あなたは職務分析およびスキル体系設計の専門家です。

以下の主な職務および必要知識・スキルを分析し、
企業共通で利用可能なスキルマスタを作成してください。

【目的】

人材ポートフォリオおよび職務類似度分析で利用できる共通スキル体系を作成する。

【ルール】

- ポジション名や部署名は考慮しない
- タスク名をそのままスキル名にしない
- 職務の背後にある能力を抽出する
- 同義語や類似概念は統合する
- 特定システム名や製品名は汎化する
- 将来的に全社員を同じ軸で比較できる粒度とする
- スキル数は10〜20個とする
- スキル同士が重複しないこと（MECEを意識）
- 個別業務ではなく再利用可能な能力として定義すること

【期待する粒度】

良い例
- 戦略立案
- 業務企画
- プロジェクト管理
- データ分析
- 業務改善
- 品質管理
- 生産管理
- コミュニケーション
- リーダーシップ

悪い例
- 会議資料作成
- 週次レポート作成
- Excel集計
- SAP入力

【出力形式】

{
  "skills": [
    {
      "skill_name": "",
      "definition": ""
    }
  ]
}

以下が分析対象データです:
{records}
"""


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Lambdaエントリポイント。

    処理概要:
    1. 入力イベントからS3のバケット/キーを解決
    2. CSVを取得して固定列(A-F)を抽出
    3. Bedrock Claudeへプロンプトを送信しスキルマスタ生成
    4. 生成結果をDynamoDBへ保存
    """
    logger.info("Received event")

    model_id = os.environ.get("BEDROCK_MODEL_ID")
    bucket_name = os.environ.get("S3_BUCKET_NAME")
    table_name = os.environ.get("SKILL_MASTER_TABLE_NAME")

    if not model_id or not bucket_name or not table_name:
        logger.error("Missing required environment variables")
        return _error_response(500, "Required environment variables are missing")

    try:
        source_bucket, source_key = _resolve_s3_source(event, bucket_name)
        csv_bytes = _download_csv_from_s3(source_bucket, source_key)
        records = _extract_records_from_csv(csv_bytes)

        if not records["duties"] and not records["required_skills"]:
            logger.warning("No data found in target columns")
            return _error_response(400, "No valid rows found in CSV target columns")

        prompt = PROMPT_TEMPLATE.format(records=json.dumps(records, ensure_ascii=False))
        skill_master = _invoke_bedrock(model_id, prompt)
        saved_count = _save_skill_master(
            table_name, source_bucket, source_key, skill_master
        )

        logger.info("Saved skill master items: %s", saved_count)
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Skill master generated and saved successfully",
                    "saved_count": saved_count,
                    "source": {"bucket": source_bucket, "key": source_key},
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


def _resolve_s3_source(event: dict[str, Any], default_bucket: str) -> tuple[str, str]:
    """S3入力元を解決する。

    - S3イベント起動: Records[0].s3 から取得
    - 手動実行: event の key/s3_key, bucket/s3_bucket から取得
    """
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
    """指定されたS3オブジェクト(CSV)をバイト列で取得する。"""
    logger.info("Downloading CSV from S3: s3://%s/%s", bucket, key)
    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _extract_records_from_csv(csv_bytes: bytes) -> dict[str, list[str]]:
    """CSVからLLM入力用のデータを抽出する。

    対象:
    - 列順固定のA-F
      A-E: 主な職務#1-#5
      F: 必要知識・スキル

    ルール:
    - 主な職務は重複を保持する
    - 必要知識・スキルは重複を排除する
    """
    text = csv_bytes.decode("utf-8-sig")
    reader = csv.reader(StringIO(text))

    duties: list[str] = []
    required_skills: list[str] = []
    required_skill_seen: set[str] = set()
    csv_row_count = 0

    for index, row in enumerate(reader):
        values = [_normalize_cell(row[i]) if i < len(row) else "" for i in range(6)]

        # 先頭行がヘッダの場合のみスキップする(列名検索は行わない)。
        if index == 0 and values == [
            "主な職務#1",
            "主な職務#2",
            "主な職務#3",
            "主な職務#4",
            "主な職務#5",
            "必要知識・スキル(知識・スキル)",
        ]:
            continue

        if not any(values):
            continue

        csv_row_count += 1

        for duty in values[:5]:
            if duty:
                duties.append(duty)

        required_skill = values[5]
        if required_skill and required_skill not in required_skill_seen:
            required_skill_seen.add(required_skill)
            required_skills.append(required_skill)

    logger.info("CSV行数: %s", csv_row_count)
    logger.info("抽出した職務件数: %s", len(duties))
    logger.info("重複排除後のスキル件数: %s", len(required_skills))

    return {"duties": duties, "required_skills": required_skills}


def _normalize_cell(value: Any) -> str:
    """セル値を文字列化し、前後空白除去と空白正規化を行う。"""
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def _invoke_bedrock(model_id: str, prompt: str) -> dict[str, Any]:
    """Bedrock Runtimeを呼び出して生成結果をJSONとして返す。"""
    logger.info("Invoking Bedrock model: %s", model_id)
    bedrock = boto3.client("bedrock-runtime")

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": prompt}],
    }

    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body, ensure_ascii=False),
        contentType="application/json",
        accept="application/json",
    )

    payload = json.loads(response["body"].read())
    generated_text = _extract_bedrock_text(payload)
    return _parse_skill_master_json(generated_text)


def _extract_bedrock_text(payload: dict[str, Any]) -> str:
    """Bedrockレスポンスから生成テキスト本体を取り出す。"""
    content = payload.get("content")
    if isinstance(content, list) and content:
        text = content[0].get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    output_text = payload.get("outputText")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    raise ValueError("Unable to extract text from Bedrock response")


def _parse_skill_master_json(text: str) -> dict[str, Any]:
    """LLM出力JSONを検証・正規化する。

    - Markdownコードフェンス付きJSONにも対応
    - skills配列の形式を検証
    - 0件のみエラーとし、10〜20件の範囲外はwarningを出す
    """
    json_text = text.strip()

    # Claudeが```json ... ```形式で返すケースに対応する。
    if json_text.startswith("```"):
        json_text = re.sub(r"^```(?:json)?", "", json_text).strip()
        json_text = re.sub(r"```$", "", json_text).strip()

    data = json.loads(json_text)
    skills = data.get("skills")

    if not isinstance(skills, list):
        raise ValueError("Bedrock output does not contain valid 'skills' array")

    normalized_skills: list[dict[str, str]] = []
    for item in skills:
        if not isinstance(item, dict):
            continue
        skill_name = _normalize_cell(item.get("skill_name"))
        definition = _normalize_cell(item.get("definition"))
        if skill_name and definition:
            normalized_skills.append(
                {"skill_name": skill_name, "definition": definition}
            )

    skill_count = len(normalized_skills)
    if skill_count == 0:
        raise ValueError("Generated skills count must be at least 1")

    if not (10 <= skill_count <= 20):
        logger.warning(
            "Generated skills count is outside recommended range (10-20): %s",
            skill_count,
        )

    return {"skills": normalized_skills}


def _save_skill_master(
    table_name: str, source_bucket: str, source_key: str, skill_master: dict[str, Any]
) -> int:
    """スキルマスタをDynamoDBに保存し、保存件数を返す。"""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)

    now = datetime.now(timezone.utc).isoformat()
    count = 0

    with table.batch_writer() as batch:
        for skill in skill_master["skills"]:
            skill_name = skill["skill_name"]
            definition = skill["definition"]
            skill_id = str(uuid.uuid5(uuid.NAMESPACE_URL, skill_name))

            batch.put_item(
                Item={
                    "skillId": skill_id,
                    "skillName": skill_name,
                    "definition": definition,
                    "updatedAt": now,
                    "sourceBucket": source_bucket,
                    "sourceKey": source_key,
                }
            )
            count += 1

    return count


def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """エラーレスポンスの共通フォーマットを生成する。"""
    return {
        "statusCode": status_code,
        "body": json.dumps({"message": message}, ensure_ascii=False),
    }
