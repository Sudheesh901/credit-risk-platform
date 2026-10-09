# Project Status

_Last updated: 2026-10-09 (about day 3 of a 6-week plan)._

## Summary

Setup is complete, the bronze layer is built and profiled, and the silver layer now holds cleaned origination features and a validated 24-month default label. Twenty-five automated data-quality checks pass on the silver layer. The next work is loading the data into S3 and Athena to finish Week 1.

## Done

**Setup**
- [x] Project folders, Python 3.11 environment (DuckDB, pandas, pyarrow), Git repo on GitHub
- [x] AWS account secured: MFA on the root user, a separate admin user with MFA, budget alerts (monthly cost and zero-spend), working region us-east-1

**Week 1: data lake**
- [x] Downloaded Freddie Mac SFLLD sample files and header files for vintages 2013-2022
- [x] Inspected files and mapped the 31 origination and 35 performance columns to the sample rows
- [x] Built the bronze layer: all-text Parquet with named columns, partitioned by `vintage_year` (`ingest/to_parquet.py`)
- [x] Profiled the bronze data (`ingest/profile_bronze.py`)
- [x] Built the silver layer: typed columns, placeholders turned into missing values, unusable column dropped (`ingest/build_silver.py`)
- [x] Found and fixed a calendar effect in the first default label (`ingest/diagnose_default_timing.py`)
- [x] Wrote automated data-quality checks for the silver layer; all 25 pass (`ingest/check_quality.py`)
- [x] Diagnosed the first check failures and corrected the rules (`ingest/diagnose_quality_failures.py`)

## Data profiling findings (2013-2022 samples)

- 10 vintages x 50,000 loans = **500,000 loans** and about **28.3 million** monthly performance rows. Every performance loan has an origination record, and loan IDs are unique.
- Raw text shrank about 10x when stored as Parquet (for example 450 MB to 40 MB).
- **Delinquency status** (`dq_status`) is stored in months past due: `00` is current, `01` is 30 days, `02` is 60, `03` is 90, and so on. `RA` marks a loan acquired as real-estate-owned.
- **Why loans ended** (`zero_bal_code`): about 308,000 loans have ended. Almost all are code `01` (prepaid or matured, 304,980). Credit-event endings (codes `02`, `03`, `09`, `15`) total only about 1,076 loans. Codes `96` and `16` are rare and need checking against the User Guide.
- **Placeholder values** converted to missing:
  - `fico`: `9999` (77 loans)
  - `dti`: `999` (30,602 loans, about 6%), kept as a `dti_missing` flag
  - `ltv` and `cltv`: `999` (4 and 5 loans)
  - `vantage_score`: `9999` for every loan, so the column is dropped

## Default label investigation

The first version of the 24-month default label (90+ days delinquent, real-estate-owned, or a credit-event ending) gave default rates of 2.67% for the 2018 vintage and 4.63% for 2019, against 0.65% to 1.03% for 2013-2017.

A timing check showed those defaults were concentrated in calendar 2020 (1,083 first defaults for 2018 loans and 1,998 for 2019 loans), and about 90% of first-default events dated 2020 carried forbearance and disaster flags. The jump came from pandemic forbearance, not from weaker loans.

**Fix:** the adjusted label ignores 90+ day delinquency while a loan is in forbearance or flagged as disaster-related. Credit-event endings and real-estate-owned acquisitions always count. Both versions are stored: `default_24m` (adjusted) and `default_24m_raw`.

| Vintage | Raw default rate | Adjusted default rate | Ever in forbearance (24 months) |
|---|---|---|---|
| 2013 | 0.65% | 0.59% | 0.13% |
| 2014 | 0.74% | 0.66% | 0.18% |
| 2015 | 0.69% | 0.55% | 0.37% |
| 2016 | 0.81% | 0.59% | 0.63% |
| 2017 | 1.03% | 0.83% | 0.65% |
| 2018 | 2.67% | 0.74% | 4.29% |
| 2019 | 4.63% | 0.66% | 6.52% |
| 2020 | 1.66% | 0.45% | 2.04% |
| 2021 | 0.97% | 0.55% | 0.88% |
| 2022 | 1.85% | 1.44% | 1.20% |

**Results**
- Adjusted rates for 2018 and 2019 fall to 0.74% and 0.66%, in line with 2013-2017.
- The credit score gradient is stronger with the adjusted label: 2.83% for scores below 680 down to 0.22% for 760+ (about 13x), against 4.68% to 0.63% raw (about 7x).
- The 2022 vintage stays higher at 1.44%. The adjustment removes only about a fifth of its raw defaults, against roughly 72% for 2018 and 86% for 2019, so this looks like genuine deterioration. It is a candidate scenario for the drift-monitoring demo, to be examined rather than assumed.
- Total adjusted defaults: 3,538 of 500,000 loans (0.71%). By split: about 1,202 in training years 2013-2016, 415 in validation 2017, 371 in the 2018 out-of-time test. These counts are thin, so test metrics on the samples will be noisy until full vintage files are used.
- **Known limitation:** a loan that entered forbearance and truly failed later, or while flagged, is labelled non-default. This will be documented in the model card.

## Data-quality findings

The first run of the checks passed 18 of 22 rules. The four failures were investigated rather than silenced:

- **270 loans with only a month-0 record:** each has a single performance row, and almost all (263) ended immediately as prepaid or matured. They are valid, so the rule was changed to require that such loans stay rare (0.054% now).
- **LTV above 105 (and CLTV above 200):** every such loan is a HARP refinance (4,728 loans in the samples, LTV up to 528). HARP had no LTV cap. Non-HARP loans never exceed LTV 105 or CLTV 200, and the checks now test HARP and non-HARP loans separately.
- **One HARP loan with CLTV above 700:** left visible in the check output (at most 5 allowed) and to be capped during feature engineering rather than deleted.
- **69 loans with a first payment more than a year from the vintage (0.014%):** dates are internally consistent, so these are unusual loans; a small tolerance is allowed.

## Decisions so far

- Bronze layer is kept as raw text; typing and cleaning happen in the silver layer.
- Data is partitioned Hive-style by `vintage_year` so Athena can read it directly.
- Default label: flag-adjusted 24-month definition (see above), with the raw version kept for comparison.
- Split by origination year: train 2013-2016, validate 2017, out-of-time test 2018, 2019 spare, replay and drift stream 2020-2022.
- HARP refinance loans (the only loans with LTV above 105) are kept and flagged for now. Week 2 decides whether to model them separately, exclude them, or keep them with the flag.
- Extreme LTV and CLTV values are handled by capping at a high percentile during feature engineering, not by deleting loans.

## Next steps

1. Upload to S3 and create Athena tables (Week 1 definition of done: an Athena query returns the default rate by vintage)
2. Week 2: feature engineering (including the HARP decision and capping extreme values), scorecard vs LightGBM, calibration, SHAP

## Open items and risks

- Confirm zero-balance codes `96` and `16`, and how to treat modified loans, in the User Guide
- Upgrade the AWS account to the Paid plan before Week 3 (SageMaker), and check the credits balance weekly
- Thin default counts in the samples: plan to retrain on full vintage files
- Investigate why the 2022 vintage has higher defaults
- Decide how to treat HARP loans in modelling (Week 2)
