# Project Status

_Last updated: 2026-10-09 (about day 3 of a 6-week plan)._

## Summary

Setup is complete and the raw data has been converted into a clean bronze layer. The next work is the silver layer (typed columns, placeholders turned into missing values), the default label, data-quality checks, and loading the data into S3 and Athena.

## Done

**Setup**
- [x] Project folders, Python 3.11 environment (DuckDB, pandas, pyarrow), Git repo on GitHub
- [x] AWS account secured: MFA on the root user, a separate admin user with MFA, budget alerts (monthly cost and zero-spend), working region us-east-1

**Week 1: data lake**
- [x] Downloaded Freddie Mac SFLLD sample files and header files for vintages 2013-2022
- [x] Inspected files and mapped the 31 origination and 35 performance columns to the sample rows
- [x] Built the bronze layer: all-text Parquet with named columns, partitioned by `vintage_year` (`ingest/to_parquet.py`)
- [x] Profiled the bronze data (`ingest/profile_bronze.py`)

## Data profiling findings (2013-2022 samples)

- 10 vintages x 50,000 loans = **500,000 loans** and about **28.3 million** monthly performance rows. Every performance loan has an origination record, and loan IDs are unique.
- Raw text shrank about 10x when stored as Parquet (for example 450 MB to 40 MB).
- **Delinquency status** (`dq_status`) is stored in months past due: `00` is current, `01` is 30 days, `02` is 60, `03` is 90, and so on. `RA` marks a loan acquired as real-estate-owned.
- **Why loans ended** (`zero_bal_code`): about 308,000 loans have ended. Almost all are code `01` (prepaid or matured, 304,980). Credit-event endings (codes `02`, `03`, `09`, `15`) total only about **1,076 loans, roughly 0.2%**. Codes `96` and `16` are rare and need checking against the User Guide.
- **Placeholder values** that must become missing:
  - `fico`: `9999` (77 loans)
  - `dti`: `999` (30,602 loans, about 6%)
  - `ltv` and `cltv`: `999` (a handful of loans)
  - `vantage_score`: `9999` for every loan, so the column is unusable in these vintages and will be dropped
- **Implication:** defaults are rare, so the 50,000-loan samples will give only a limited number of defaults per vintage. Use the samples to build and test the pipeline, then train the final model on full vintage files.

## Decisions so far

- Bronze layer is kept as raw text; typing and cleaning happen in a separate silver layer.
- Data is partitioned Hive-style by `vintage_year` so Athena can read it directly.
- Draft split by origination year: train 2013-2016, validate 2017, out-of-time test 2018, 2019 spare, replay and drift stream 2020-2022.
- Draft default definition (to be confirmed against the Freddie Mac User Guide): within 24 months of origination, the loan reaches 90+ days delinquent, becomes real-estate-owned, or ends with a credit-event zero-balance code. Loans that prepay are labelled non-default.

## Next steps

1. Silver layer: typed columns, placeholders to missing, dropped unusable columns
2. Compute the default label per loan and report default rates by vintage
3. Data-quality checks
4. Upload to S3 and create Athena tables (Week 1 definition of done: an Athena query returns default rate by vintage)

## Open items and risks

- Confirm zero-balance codes `96` and `16`, and how to treat modified loans, in the User Guide
- Upgrade the AWS account to the Paid plan before Week 3 (SageMaker), and check the credits balance weekly
- Thin default counts in the samples (see above)
