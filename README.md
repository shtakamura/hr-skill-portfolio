# HR Skill Portfolio

## Overview

職務情報から共通スキルマスタを生成し、
ポジション別スキルレベルおよびポジションカバー度を可視化するPoC。

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

- ポジションカバー度計算

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

## Position Coverage Calculation

ポジションカバー度は、選択ポジションの中核スキル要件を他ポジションがどの程度満たすかで算出する。

使用指標

- Core Skill Level Coverage

計算式

coverage(A,B) = coveredCoreSkillCount(A,B) / selectedCoreSkillCount(A)

A：選択ポジション

B：比較ポジション

例

Aの中核スキル = {営業マネジメント:5, 顧客関係管理:4, 戦略立案:4, リーダーシップ:5}

Bの該当スキルレベル = {営業マネジメント:5, 顧客関係管理:5, 戦略立案:3, リーダーシップ:4}

カバー済み中核スキル = 2

選択ポジションの中核スキル = 4

カバー度 = 2 / 4 = 0.5

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

## GitHub Actions + AWS OIDC Configuration

### 概要

GitHub Actions から AWS へセキュアにデプロイするため、AWS Identity and Access Management (IAM) の OIDC フェデレーション機能を使用しています。

これにより、AWS アクセスキーを GitHub Secrets に保存することなく、一時的な認証情報を使用して CDK デプロイを実行できます。

### アーキテクチャ

```
GitHub Actions
    ↓
GitHub OIDC Token
    ↓
AWS OIDC Provider
    ↓
AWS IAM Role
    ↓
CDK Deploy (CloudFormation)
```

### コンポーネント

**1. GitHub OIDC Provider**
- URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`
- GitHub Actions が発行するトークンを信頼できる認証局として登録

**2. GitHub Actions デプロイロール**
- ロール名: `HrSkillPortfolioGitHubActionsDeployRole`
- 信頼関係: GitHub OIDC Provider のトークンを信頼
- サブジェクト制限: `repo:shtakamura/hr-skill-portfolio:ref:refs/heads/main`
  - このリポジトリの main ブランチからのデプロイのみを許可

**3. IAM ポリシー（最小権限）**
- CloudFormation スタック管理
- Lambda 関数・実行ロール管理
- DynamoDB テーブル管理
- S3 バケット管理
- Lambda Layer 管理
- CDK Bootstrap ロール権限

AdministratorAccess は付与していません。

### GitHub Actions ワークフロー

**deploy-backend.yml**
- トリガー: `main` ブランチへのプッシュ
- パーミッション: `contents: read`, `id-token: write`
- AWS 認証: `aws-actions/configure-aws-credentials@v4` (OIDC)
- 動作: CDK デプロイ (`HrSkillPortfolioStack`)

**validate.yml**
- トリガー: Pull Request
- パーミッション: `contents: read` のみ（AWS デプロイなし）
- 動作:
  - フロントエンド ビルド
  - CDK ビルド・synth
  - バックエンド Python テスト

### セキュリティ機能

- ✅ OIDC トークンベース認証（一時認証情報）
- ✅ AWS アクセスキー不使用
- ✅ GitHub Secrets に長期アクセスキー非保存
- ✅ サブジェクト制限（main ブランチのみ）
- ✅ 最小権限ポリシー（AdministratorAccess 非使用）
- ✅ PR では AWS デプロイ実行なし

### デプロイ手順

1. **AWS アカウント ID を GitHub Secret に設定**（実装は別途実施）
   - Secret 名: `AWS_ACCOUNT_ID`

2. **CDK デプロイ**
   ```bash
   cd infra/cdk
   npm run build
   npx cdk deploy GitHubActionsOidcStack --require-approval never
   npx cdk deploy HrSkillPortfolioStack --require-approval never
   ```

3. **GitHub へプッシュ**
   ```bash
   git push origin main
   ```

4. **GitHub Actions ワークフロー実行**
   - `deploy-backend.yml` が自動実行
   - OIDC トークンを使用して AWS にデプロイ
