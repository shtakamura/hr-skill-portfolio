import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
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

    const frontendBucket = new s3.Bucket(this, "FrontendBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
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

    const organizationMasterTable = new dynamodb.Table(this, "OrganizationMasterTable", {
      tableName: "OrganizationMaster",
      partitionKey: {
        name: "organizationId",
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    const positionMasterTable = new dynamodb.Table(this, "PositionMasterTable", {
      tableName: "PositionMaster",
      partitionKey: {
        name: "positionId",
        type: dynamodb.AttributeType.STRING
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY
    });

    positionMasterTable.addGlobalSecondaryIndex({
      indexName: "organizationId-index",
      partitionKey: {
        name: "organizationId",
        type: dynamodb.AttributeType.STRING
      },
      projectionType: dynamodb.ProjectionType.ALL
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

    const evaluatePositionSkillFunction = new lambda.Function(this, "EvaluatePositionSkillFunction", {
      functionName: "evaluate-position-skill",
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset("../../backend/lambda/generate-position-skill"),
      handler: "app.handler",
      memorySize: 1024,
      timeout: cdk.Duration.seconds(120),
      environment: {
        BEDROCK_MODEL_ID: "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
        S3_BUCKET_NAME: portfolioBucket.bucketName,
        SKILL_MASTER_TABLE_NAME: skillMasterTable.tableName,
        POSITION_SKILL_TABLE_NAME: positionSkillTable.tableName,
        ORGANIZATION_MASTER_TABLE_NAME: organizationMasterTable.tableName,
        POSITION_MASTER_TABLE_NAME: positionMasterTable.tableName
      }
    });

    const getPositionMasterFunction = new lambda.Function(this, "GetPositionMasterFunction", {
      functionName: "get-position-master",
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset("../../backend/lambda/get-position-master"),
      handler: "app.handler",
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        ORGANIZATION_MASTER_TABLE_NAME: organizationMasterTable.tableName,
        POSITION_MASTER_TABLE_NAME: positionMasterTable.tableName,
        CORS_ALLOW_ORIGIN: "http://localhost:5173"
      }
    });

    const getPositionSkillsFunction = new lambda.Function(this, "GetPositionSkillsFunction", {
      functionName: "get-position-skills",
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset("../../backend/lambda/get-position-skills"),
      handler: "app.handler",
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: {
        POSITION_SKILL_TABLE_NAME: positionSkillTable.tableName,
        CORS_ALLOW_ORIGIN: "http://localhost:5173"
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

    skillMasterTable.grantReadData(evaluatePositionSkillFunction);
    positionSkillTable.grantWriteData(evaluatePositionSkillFunction);
    organizationMasterTable.grantReadWriteData(evaluatePositionSkillFunction);
    positionMasterTable.grantReadWriteData(evaluatePositionSkillFunction);
    portfolioBucket.grantRead(evaluatePositionSkillFunction);
    evaluatePositionSkillFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ["bedrock:InvokeModel"],
        resources: ["*"]
      })
    );

    positionSkillTable.grantReadData(getPositionSkillsFunction);
  organizationMasterTable.grantReadData(getPositionMasterFunction);
  positionMasterTable.grantReadData(getPositionMasterFunction);

    const api = new apigateway.RestApi(this, "HrSkillPortfolioApi", {
      restApiName: "hr-skill-portfolio-api",
      deployOptions: {
        stageName: "prod"
      },
      defaultCorsPreflightOptions: {
        allowOrigins: ["http://localhost:5173"],
        allowMethods: ["GET", "OPTIONS"],
        allowHeaders: ["Content-Type", "Authorization"]
      }
    });

    api.root
      .addResource("position-skills")
      .addMethod("GET", new apigateway.LambdaIntegration(getPositionSkillsFunction));

    api.root
      .addResource("organizations")
      .addMethod("GET", new apigateway.LambdaIntegration(getPositionMasterFunction));

    api.root
      .addResource("positions")
      .addMethod("GET", new apigateway.LambdaIntegration(getPositionMasterFunction));

    const distribution = new cloudfront.Distribution(this, "FrontendDistribution", {
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(frontendBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED
      },
      additionalBehaviors: {
        organizations: {
          origin: new origins.HttpOrigin(
            `${api.restApiId}.execute-api.${cdk.Stack.of(this).region}.${cdk.Stack.of(this).urlSuffix}`,
            { originPath: `/${api.deploymentStage.stageName}` }
          ),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
        },
        positions: {
          origin: new origins.HttpOrigin(
            `${api.restApiId}.execute-api.${cdk.Stack.of(this).region}.${cdk.Stack.of(this).urlSuffix}`,
            { originPath: `/${api.deploymentStage.stageName}` }
          ),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
        },
        "position-skills": {
          origin: new origins.HttpOrigin(
            `${api.restApiId}.execute-api.${cdk.Stack.of(this).region}.${cdk.Stack.of(this).urlSuffix}`,
            { originPath: `/${api.deploymentStage.stageName}` }
          ),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
        }
      },
      errorResponses: [
        {
          httpStatus: 403,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.minutes(5)
        },
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: "/index.html",
          ttl: cdk.Duration.minutes(5)
        }
      ]
    });

    new s3deploy.BucketDeployment(this, "FrontendDeployment", {
      sources: [s3deploy.Source.asset("../../frontend/dist")],
      destinationBucket: frontendBucket,
      distribution,
      distributionPaths: ["/index.html", "/assets/*"]
    });

    portfolioBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(generateSkillMasterFunction),
      { prefix: "skill-master-input/", suffix: ".csv" }
    );

    portfolioBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(evaluatePositionSkillFunction),
      { prefix: "position-input/", suffix: ".csv" }
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

    new cdk.CfnOutput(this, "OrganizationMasterTableName", {
      value: organizationMasterTable.tableName
    });

    new cdk.CfnOutput(this, "PositionMasterTableName", {
      value: positionMasterTable.tableName
    });

    new cdk.CfnOutput(this, "GenerateSkillMasterFunctionName", {
      value: generateSkillMasterFunction.functionName
    });

    new cdk.CfnOutput(this, "EvaluatePositionSkillFunctionName", {
      value: evaluatePositionSkillFunction.functionName
    });

    new cdk.CfnOutput(this, "GetPositionSkillsFunctionName", {
      value: getPositionSkillsFunction.functionName
    });

    new cdk.CfnOutput(this, "GetPositionMasterFunctionName", {
      value: getPositionMasterFunction.functionName
    });

    new cdk.CfnOutput(this, "ApiUrl", {
      value: api.url
    });

    new cdk.CfnOutput(this, "FrontendBucketName", {
      value: frontendBucket.bucketName
    });

    new cdk.CfnOutput(this, "FrontendDistributionDomainName", {
      value: distribution.distributionDomainName
    });
  }
}
