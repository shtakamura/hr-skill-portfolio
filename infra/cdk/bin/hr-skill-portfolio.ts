#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { HrSkillPortfolioStack } from "../lib/hr-skill-portfolio-stack";
import { GitHubActionsOidcStack } from "../lib/github-actions-oidc-stack";

const app = new cdk.App();

new GitHubActionsOidcStack(app, "GitHubActionsOidcStack", {
  description: "OIDC configuration for GitHub Actions to deploy HR skill portfolio"
});

new HrSkillPortfolioStack(app, "HrSkillPortfolioStack", {
  description: "PoC infrastructure for HR skill portfolio using Bedrock, Lambda, DynamoDB, and S3"
});
