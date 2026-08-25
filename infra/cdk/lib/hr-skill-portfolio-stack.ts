import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";

export class HrSkillPortfolioStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const portfolioBucket = new s3.Bucket(this, "PortfolioBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    const skillMasterTable = new dynamodb.Table(this, "SkillMasterTable", {
      tableName: "SkillMaster",
      partitionKey: {
        name: "skillId",
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    const positionSkillTable = new dynamodb.Table(this, "PositionSkillTable", {
      tableName: "PositionSkill",
      partitionKey: {
        name: "positionId",
        type: dynamodb.AttributeType.STRING
      },
      sortKey: {
        name: "skillId",
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    const generateSkillMasterFunction = new lambda.Function(this, "GenerateSkillMasterFunction", {
      functionName: "generate-skill-master",
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset("../../backend/lambda/generate-skill-master"),
      handler: "app.handler",
      memorySize: 1024,
      timeout: cdk.Duration.seconds(120),
      environment: {
        BEDROCK_MODEL_ID: "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
        S3_BUCKET_NAME: portfolioBucket.bucketName,
        SKILL_MASTER_TABLE_NAME: skillMasterTable.tableName
      }
    });

    skillMasterTable.grantReadWriteData(generateSkillMasterFunction);
    portfolioBucket.grantRead(generateSkillMasterFunction);
    generateSkillMasterFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: ["*"]
      })
    );

    portfolioBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(generateSkillMasterFunction),
      { suffix: ".csv" }
    );

    new cdk.CfnOutput(this, "PortfolioBucketName", {
      value: portfolioBucket.bucketName
    });

    new cdk.CfnOutput(this, "SkillMasterTableName", {
      value: skillMasterTable.tableName
    });

    new cdk.CfnOutput(this, "PositionSkillTableName", {
      value: positionSkillTable.tableName
    });

    new cdk.CfnOutput(this, "GenerateSkillMasterFunctionName", {
      value: generateSkillMasterFunction.functionName
    });
  }
}
