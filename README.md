# HR Skill Portfolio

## Overview

職務情報から共通スキルマスタを生成し、
ポジション別スキルレベルおよび職務類似度を可視化するPoC。

## Architecture

Excel
↓
Amazon S3
↓
AWS Lambda
↓
Amazon Bedrock (Claude)

- スキルマスタ生成
- ポジション別スキルレベル判定

↓
Amazon DynamoDB

↓
AWS Lambda

- 類似度計算

↓
React Frontend

## Skill Master Generation

入力

- 主な職務①〜⑤
- 必要知識・スキル

出力

- スキル名
- スキル定義

生成数

- 10〜20個

実装

- Lambda: `generate-skill-master` (Python)
- 実装配置: `backend/lambda/generate-skill-master`
- 入力: S3にアップロードされたExcel (`SF_ポジション定義` シート)
- 処理: A〜F列を集約し、Bedrock Claudeで共通スキルマスタを生成
- 保存先: DynamoDB `SkillMaster`

環境変数

- `BEDROCK_MODEL_ID`
- `S3_BUCKET_NAME`
- `SKILL_MASTER_TABLE_NAME`

## Skill Level Definition

5：会社レベルで高度に活用し、全社展開・標準化を推進できる

4：他者を指導し、チームとして成果を上げられる

3：自律的に遂行できる

2：助言を受けながら遂行できる

1：基礎知識を理解している

0：知識・経験がない

## Similarity Calculation

職務類似度はスキル保有状況をもとに算出する。

使用指標

- Jaccard Similarity

計算式

J(A,B) = |A ∩ B| / |A ∪ B|

A：ポジションAのスキル集合

B：ポジションBのスキル集合

例

A = {戦略立案, 業務企画, コミュニケーション}

B = {戦略立案, データ分析, コミュニケーション}

共通スキル = 2

全スキル = 4

類似度 = 2 / 4 = 0.5

## Tech Stack

Frontend

- React
- TypeScript
- Vite
- Material UI

Backend

- AWS Lambda
- Amazon Bedrock (Claude)
- API Gateway
- DynamoDB
- S3

Infrastructure

- AWS CDK

CI/CD

- GitHub Actions
