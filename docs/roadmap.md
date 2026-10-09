# Roadmap

Six-week plan, started 2026-10-07. Dates are targets and are adjusted as the work moves. Current progress is tracked in [status.md](status.md).

## Goal

Build and deploy an end-to-end credit risk platform on AWS using the Freddie Mac Single-Family Loan-Level Dataset: a data lake, a governed probability-of-default model, a live scoring API, stream-replay scoring, and monitoring with automated retraining.

## Milestones

- **Milestone 1 (target Nov 4):** live scoring API, public repository, write-up and first LinkedIn post
- **Milestone 2 (target Nov 18):** full lifecycle live, including the replay stream, monitoring dashboards and the retraining loop

## Phases

| Week | Dates | Focus | Definition of done |
|---|---|---|---|
| 0 | Oct 7-9 | Setup: local environment, GitHub, AWS account security and budgets | **Done** |
| 1 | Oct 7-14 | Data lake: bronze, silver, default label, quality checks, S3 and Athena | Athena query returns the default rate by vintage |
| 2 | Oct 14-21 | Modelling: features, scorecard vs LightGBM, calibration, SHAP, threshold economics | Model comparison table on the 2018 out-of-time test set, calibration plot, draft model card |
| 3 | Oct 21-28 | SageMaker lifecycle and Terraform: Processing, Spot training, Clarify, Pipeline, Model Registry | An approved model version in the registry, infra reproducible with Terraform |
| 4 | Oct 28-Nov 4 | Serving and CI/CD: container, ECR, Lambda, API Gateway, GitHub Actions (OIDC), tests | **Milestone 1:** API live, load tested, champion/challenger alias, write-up published |
| 5 | Nov 4-11 | Streaming replay and orchestration: EventBridge Scheduler, SQS, Lambda scorer, Step Functions | Replayed months scored automatically and queryable in Athena |
| 6 | Nov 11-18 | Monitoring and launch: PSI/CSI, delayed-label performance, CloudWatch dashboard and alarms, retrain trigger, runbook | **Milestone 2:** alarm triggers retraining and the new model is promoted through the registry |

## Modelling design

- **Unit of analysis:** one row per loan, features from origination data.
- **Default label (adopted):** within 24 months of origination the loan ends with a credit-event zero-balance code (`02`, `03`, `09`, `15`), is acquired as real-estate-owned, or reaches 90+ days delinquent while not in forbearance and not flagged as disaster-related. The first version ignored those flags and was inflated for the 2018 and 2019 vintages by pandemic forbearance (see [status.md](status.md)), so the raw version is kept as `default_24m_raw` for comparison. Prepaid loans are labelled non-default.
- **Splits by origination year:** train 2013-2016, validation 2017, out-of-time test 2018, 2019 spare, replay and drift stream 2020-2022. On the 50,000-loan samples the adjusted defaults are about 1,200 (train), 415 (validation) and 371 (test), so sample metrics are noisy and the final model is retrained on full vintages. The 2022 vintage shows genuinely higher defaults and is the natural drift scenario for the monitoring demo.
- **Models:** weight-of-evidence logistic scorecard as the benchmark, LightGBM with monotonic constraints as the challenger.
- **Evaluation:** AUC, KS, Gini, Brier score, calibration curve, stability across vintages, cost-based approval threshold.
- **Explainability:** SHAP reason codes per decision, Clarify reports.
- **Monitoring:** PSI on score and features, CSI by feature, realised default rate as labels mature, champion/challenger comparison.
- **Data scale:** build and test on the 50,000-loan samples, then retrain on full vintage files.

## Architecture

| Tier | Services |
|---|---|
| Data lake | S3, Athena, Glue Data Catalog |
| Train and govern | SageMaker Processing, Training, Clarify, Pipelines, Model Registry |
| Deploy and serve | GitHub Actions (OIDC), ECR, Lambda container, API Gateway |
| Stream, orchestrate, monitor | EventBridge Scheduler, SQS, Step Functions, CloudWatch |
| Across all tiers | Terraform, IAM, KMS, CloudTrail, Budgets |

## Cost guardrails

- Budget alerts are set; credits balance is checked weekly
- No always-on SageMaker endpoints; scoring runs on Lambda
- Short SageMaker jobs on small instances, Spot where possible
- Athena workgroup scan limit and S3 lifecycle rules
- Tear down streaming resources after each demo (Terraform destroy)

## Stretch goals

- Loss given default and exposure at default models from the loss fields, combined into expected loss
- Macroeconomic features joined by month
- Survival model for time-to-default
- Streamlit or static demo page on top of the API

## Out of scope

- Real customer data, real lending decisions, or financial advice
- Redistribution of Freddie Mac data