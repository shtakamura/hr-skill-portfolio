# HR Skill Portfolio CDK

This CDK project defines the base PoC infrastructure for:

- S3 Bucket
- DynamoDB table: SkillMaster
- DynamoDB table: PositionSkill
- Lambda function: generate-skill-master (Python)

## generate-skill-master Lambda

Trigger:

- S3 ObjectCreated (`.csv`) on the portfolio bucket

Responsibilities:

- Read CSV (fixed columns A-F)
- Aggregate job duties and required knowledge/skills
- Invoke Amazon Bedrock Claude
- Save generated skill master into `SkillMaster`

### Environment Variables

- `BEDROCK_MODEL_ID`: Bedrock model ID for Claude
- `S3_BUCKET_NAME`: input bucket name
- `SKILL_MASTER_TABLE_NAME`: DynamoDB table name

### Lambda Files

- `../../backend/lambda/generate-skill-master/app.py`
- `../../backend/lambda/generate-skill-master/requirements.txt`

## Packaging Note (Python dependencies)

This stack uses `lambda.Code.fromAsset`, so dependencies in `requirements.txt` must be packaged into the deployment asset.

Example (PowerShell):

```powershell
Set-Location .\backend\lambda\generate-skill-master
python -m pip install -r requirements.txt -t .
```

## Commands

- `npm.cmd install`
- `npm.cmd run build`
- `npm.cmd run cdk -- synth`
- `npm.cmd run cdk -- deploy`
