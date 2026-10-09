# Credit Risk Platform

An end-to-end credit risk (probability of default) modelling project built on real US mortgage data and deployed on AWS. It covers the full machine learning lifecycle: a data lake, model training and governance, a scoring API, stream-replay scoring, and live drift and performance monitoring with delayed labels.

> **Status: in progress.**

## Why this project

Most credit scoring portfolio projects stop at a notebook with an AUC score. This one is built around what lenders and risk teams actually care about:

- Validation by origination vintage (out-of-time testing), not random splits
- Calibrated probabilities and a cost-based approval threshold
- Explainability (reason codes) and stability checks
- Production serving, CI/CD and infrastructure as code
- Monitoring with delayed ground truth: drift (PSI/CSI) now, realised performance as labels mature

## Data

- **Source:** Freddie Mac Single-Family Loan-Level Dataset (SFLLD), Standard dataset, available free after registration on Freddie Mac's Clarity site and subject to Freddie Mac's terms of use.
- **Not included in this repo.** The `data/` folder is git-ignored and the dataset must not be redistributed. The public API serves model scores only, never loan-level data.
- **Development data:** the 50,000-loan sample file for each origination year 2013-2022. The final model will use full vintage files.
- **Two file types per vintage:**
  - Origination: one row per loan, 31 columns (credit score, DTI, LTV, interest rate, state, purpose, and so on)
  - Monthly performance: one row per loan per month, 35 columns (delinquency status, balance, zero-balance code, and so on)
- Files are pipe-delimited with no header row. Column names come from separate header files supplied by Freddie Mac.

## Planned architecture

| Tier | AWS services |
|---|---|
| Data lake | S3 (raw and curated Parquet), Athena, Glue Data Catalog |
| Train and govern | SageMaker Processing, Training, Clarify, Pipelines, Model Registry |
| Deploy and serve | GitHub Actions (OIDC), ECR, Lambda container, API Gateway |
| Stream, orchestrate, monitor | EventBridge Scheduler, SQS, Step Functions, CloudWatch |
| Across all tiers | Terraform, IAM, KMS, CloudTrail, Budgets |

The monthly performance history is **replayed** as a stream (one simulated month per tick) to exercise scoring and monitoring. It is a stream-replay architecture, not live data.

## Repository layout

```
credit-risk-platform/
├── ingest/              # inspect files, read headers, convert raw files to Parquet, profile data
├── data/                # git-ignored: raw files, bronze and silver Parquet
├── docs/                # git-ignored PDFs from Freddie Mac; project docs
├── README.md
├── status.md            # what is done, findings, next steps
└── roadmap.md           # phased plan with target dates
```

More folders (`infra/terraform`, `src`, `pipelines`, `tests`, `.github/workflows`) are added as phases land.

## Getting started (current state)

```bash
git clone https://github.com/Sudheesh901/credit-risk-platform.git
cd credit-risk-platform
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install pandas pyarrow duckdb jupyter
```

1. Register on Freddie Mac's Clarity site and download the SFLLD sample files (2013-2022) and the header files.
2. Place them under `data/raw/samples/` (unzip each sample into `sample_YYYY/`) and `data/raw/headers/`.
3. Run from the repository root:

```bash
python ingest/inspect_files.py     # list files and peek at their contents
python ingest/show_headers.py      # print column lists and check library versions
python ingest/to_parquet.py        # build the bronze layer in data/bronze
python ingest/profile_bronze.py    # profile values, placeholders and join integrity
python ingest/build_silver.py      # silver layer: typed features and default labels
python ingest/diagnose_default_timing.py   # timing check behind the label fix
```

## Tech stack

Python 3.11, DuckDB, Parquet, pandas, pyarrow (current). Planned: LightGBM, scikit-learn, SHAP, SageMaker, FastAPI or a Lambda handler, Terraform, GitHub Actions.

## Author

Sudheesh. This is an educational portfolio project, not financial advice and not a production lending model.
