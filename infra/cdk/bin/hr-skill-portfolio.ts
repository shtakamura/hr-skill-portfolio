#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { HrSkillPortfolioStack } from "../lib/hr-skill-portfolio-stack";

const app = new cdk.App();
new HrSkillPortfolioStack(app, "HrSkillPortfolioStack", {
  description: "PoC infrastructure for HR skill portfolio using Bedrock, Lambda, DynamoDB, and S3"
});
