import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";

export class GitHubActionsOidcStack extends cdk.Stack {
  readonly role: iam.Role;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // 既存の GitHub OIDC Provider を参照
    const providerArn = cdk.Stack.of(this).formatArn({
      service: "iam",
      region: "",
      account: cdk.Aws.ACCOUNT_ID,
      resource: "oidc-provider",
      resourceName: "token.actions.githubusercontent.com"
    });

    const provider = iam.OpenIdConnectProvider.fromOpenIdConnectProviderArn(
      this,
      "ExistingGitHubActionsOIDC",
      providerArn
    );

    // GitHub Actions用IAMロール
    this.role = new iam.Role(this, "GitHubActionsDeployRole", {
      roleName: "HrSkillPortfolioGitHubActionsDeployRole",
      assumedBy: new iam.OpenIdConnectPrincipal(provider).withConditions({
        StringEquals: {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:shtakamura@294681980/hr-skill-portfolio@1344740129:ref:refs/heads/main"
        }
      }),
      description: "Role for GitHub Actions to deploy HR Skill Portfolio CDK stack"
    });

    // CDK Bootstrap ロール互換の最小権限ポリシーを付与
    // CloudFormation スタック管理に必要な権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "cloudformation:CreateStack",
          "cloudformation:UpdateStack",
          "cloudformation:DeleteStack",
          "cloudformation:DescribeStacks",
          "cloudformation:GetTemplate",
          "cloudformation:ListStacks",
          "cloudformation:DescribeStackEvents",
          "cloudformation:CreateChangeSet",
          "cloudformation:DescribeChangeSet",
          "cloudformation:ExecuteChangeSet",
          "cloudformation:GetTemplateSummary"
        ],
        resources: ["arn:aws:cloudformation:*:*:stack/HrSkillPortfolioStack*"]
      })
    );

    // IAM ロール・ポリシー作成権限（Lambda 実行ロール用）
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "iam:CreateRole",
          "iam:UpdateRole",
          "iam:DeleteRole",
          "iam:GetRole",
          "iam:PassRole",
          "iam:PutRolePolicy",
          "iam:DeleteRolePolicy",
          "iam:GetRolePolicy",
          "iam:ListRolePolicies"
        ],
        resources: ["arn:aws:iam::*:role/hr-skill-portfolio-*"]
      })
    );

    // Lambda 関数の作成・更新・削除権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "lambda:CreateFunction",
          "lambda:DeleteFunction",
          "lambda:UpdateFunction",
          "lambda:UpdateFunctionCode",
          "lambda:GetFunction",
          "lambda:AddPermission",
          "lambda:RemovePermission"
        ],
        resources: ["arn:aws:lambda:*:*:function:*"]
      })
    );

    // DynamoDB テーブル作成・削除権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "dynamodb:CreateTable",
          "dynamodb:DeleteTable",
          "dynamodb:DescribeTable",
          "dynamodb:UpdateTable"
        ],
        resources: ["arn:aws:dynamodb:*:*:table/SkillMaster*", "arn:aws:dynamodb:*:*:table/PositionSkill*"]
      })
    );

    // S3 バケット作成・削除権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:PutBucketVersioning",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketEncryption",
          "s3:GetBucketVersioning"
        ],
        resources: ["arn:aws:s3:::*"]
      })
    );

    // S3 オブジェクト操作権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
        resources: ["arn:aws:s3:::*/*"]
      })
    );

    // Lambda Layer 管理権限
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "lambda:PublishLayerVersion",
          "lambda:DeleteLayerVersion",
          "lambda:GetLayerVersion"
        ],
        resources: ["arn:aws:lambda:*:*:layer:*"]
      })
    );

    // CloudFormation テンプレート用の S3 アクセス権限（CDK Bootstrap）
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["s3:GetObject", "s3:PutObject"],
        resources: ["arn:aws:s3:::cdk-*/*"]
      })
    );

    // STS AssumeRole 権限（必要な場合）
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["sts:AssumeRole"],
        resources: ["arn:aws:iam::*:role/cdk-*"]
      })
    );

    // ECR アクセス権限（Lambda コンテナイメージ用）
    this.role.addToPrincipalPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ],
        resources: ["arn:aws:ecr:*:*:repository/cdk-*"]
      })
    );

    // Output
    new cdk.CfnOutput(this, "GitHubActionsRoleArn", {
      value: this.role.roleArn,
      description: "ARN of the GitHub Actions deployment role"
    });

    new cdk.CfnOutput(this, "OIDCProviderArn", {
      value: provider.openIdConnectProviderArn,
      description: "ARN of the GitHub OIDC Provider"
    });
  }
}
