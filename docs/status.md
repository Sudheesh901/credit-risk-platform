# Project Status

_Last updated: 2026-10-10 (day 4 of a 6-week plan; Week 1 complete, Week 2 modelling under way)._

## Summary

Setup is complete, the bronze layer is built and profiled, and the silver layer holds cleaned origination features and a validated 24-month default label. Twenty-five automated data-quality checks pass on the silver layer, and the data is stored in a private S3 bucket and queryable in Athena. Week 1 is complete. In Week 2 the features have been explored and a modelling dataset has been built for non-HARP loans with vintage-based train, validation and test splits. The scorecard and LightGBM models are next.

## Done

**Setup**
- [x] Project folders, Python 3.11 environment (DuckDB, pandas, pyarrow), Git repo on GitHub
- [x] AWS account secured: MFA on the root user, a separate admin user with MFA, budget alerts (monthly cost and zero-spend), working region us-east-1
- [x] AWS CLI profile for local uploads, using access keys of the admin user (to be replaced with short-lived credentials in Week 3)

**Week 1: data lake**
- [x] Downloaded Freddie Mac SFLLD sample files and header files for vintages 2013-2022
- [x] Inspected files and mapped the 31 origination and 35 performance columns to the sample rows
- [x] Built the bronze layer: all-text Parquet with named columns, partitioned by `vintage_year` (`ingest/to_parquet.py`)
- [x] Profiled the bronze data (`ingest/profile_bronze.py`)
- [x] Built the silver layer: typed columns, placeholders turned into missing values, unusable column dropped (`ingest/build_silver.py`)
- [x] Found and fixed a calendar effect in the first default label (`ingest/diagnose_default_timing.py`)
- [x] Wrote automated data-quality checks for the silver layer; all 25 pass (`ingest/check_quality.py`)
- [x] Diagnosed the first check failures and corrected the rules (`ingest/diagnose_quality_failures.py`)
- [x] Created a private S3 bucket (all public access blocked) and uploaded the silver Parquet data under `silver/orig` and `silver/labels`, partitioned by `vintage_year`
- [x] Generated Athena table definitions from the Parquet schema, with partition projection (`ingest/make_athena_ddl.py`, `infra/athena/silver_tables.sql`)
- [x] Created the Athena database `credit_risk` and ran a join query that returns the default rate by vintage (Week 1 definition of done)

**Week 2: modelling**
- [x] Explored features: HARP segment, numeric ranges, default rate by category (`src/explore_features.py`)
- [x] Built the modelling dataset for non-HARP loans with vintage splits (`src/build_model_dataset.py`, output in `data/model/`)

## Data profiling findings (2013-2022 samples)

- 10 vintages x 50,000 loans = **500,000 loans** and about **28.3 million** monthly performance rows. Every performance loan has an origination record, and loan IDs are unique.
- Raw text shrank about 10x when stored as Parquet (for example 450 MB to 40 MB).
- **Delinquency status** (`dq_status`) is stored in months past due: `00` is current, `01` is 30 days, `02` is 60, `03` is 90, and so on. `RA` marks a loan acquired as real-estate-owned.
- **Why loans ended** (`zero_bal_code`): about 308,000 loans have ended. Almost all are code `01` (prepaid or matured, 304,980). Credit-event endings (codes `02`, `03`, `09`, `15`) total only about 1,076 loans. Codes `96` and `16` are rare and need checking against the User Guide.
- **Placeholder values** converted to missing:
  - `fico`: `9999` (77 loans)
  - `dti`: `999` (30,602 loans, about 6%); these turned out to be almost exactly the HARP loans (see feature exploration findings)
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
- Total adjusted defaults: 3,538 of 500,000 loans (0.71%), including HARP loans; the modelling dataset below excludes them.
- **Known limitation:** a loan that entered forbearance and truly failed later, or while flagged, is labelled non-default. This will be documented in the model card.

## Data-quality findings

The first run of the checks passed 18 of 22 rules. The four failures were investigated rather than silenced:

- **270 loans with only a month-0 record:** each has a single performance row, and almost all (263) ended immediately as prepaid or matured. They are valid, so the rule was changed to require that such loans stay rare (0.054% now).
- **LTV above 105 (and CLTV above 200):** every such loan is a HARP refinance (4,728 loans in the samples, LTV up to 528). HARP had no LTV cap. Non-HARP loans never exceed LTV 105 or CLTV 200, and the checks now test HARP and non-HARP loans separately.
- **One HARP loan with CLTV above 700:** left visible in the check output (at most 5 allowed). Now moot for modelling, because HARP loans are excluded from the modelling dataset.
- **69 loans with a first payment more than a year from the vintage (0.014%):** dates are internally consistent, so these are unusual loans; a small tolerance is allowed.

## Feature exploration findings

- **HARP loans are concentrated in early vintages and default at 3x to 5x the regular rate in the same year.**

| Vintage | HARP share of loans | HARP default rate | Non-HARP default rate |
|---|---|---|---|
| 2013 | 28.8% | 1.36% | 0.29% |
| 2014 | 14.6% | 1.83% | 0.46% |
| 2015 | 8.0% | 1.49% | 0.47% |
| 2016 | 5.1% | 1.47% | 0.55% |
| 2017 | 3.6% | 1.50% | 0.81% |
| 2018 | 1.0% | 2.54% | 0.72% |
| 2019 | 30 loans | n/a | 0.66% |
| 2020-2022 | none | n/a | 0.45%, 0.55%, 1.44% |

  A model trained on 2013-2016 would be about 14% HARP, while the validation, test and replay years have almost none, so the training data would not resemble the data the model scores.
- **`dti_missing` is the HARP flag in disguise.** Missing-DTI loans (30,602 loans, 468 defaults) and HARP loans (30,576 loans, 468 defaults) are essentially the same set, because HARP loans do not report DTI.
- **Extreme LTV and CLTV values are all HARP.** After excluding HARP, the maximum LTV is 101 and the maximum CLTV is 105.
- **Base rate drifts upward across vintages even without HARP** (0.29% in 2013 to 0.81% in 2017). A model trained on 2013-2016 will under-predict in 2017-2018 unless it is recalibrated.
- **Category signals** (default rate, whole sample):
  - Number of borrowers: one borrower 0.99%, two borrowers 0.41% (strongest categorical signal)
  - First-time buyers 0.95% vs 0.65%; cash-out refinance 0.82% vs 0.63% for no-cash-out
  - Investors default less (0.50%) than owner-occupiers (0.74%), the opposite of the usual pattern, to be checked after controlling for other features
  - Channel and number of units show almost no signal
  - Prepayment penalty and interest-only indicators are constant for every loan
  - Property valuation method (code 1: 0.42%, code 2: 0.99%, code 7 for 68% of loans) appears to reflect underwriting practice and period rather than a borrower trait

## Decisions so far

**Data and labels**
- Bronze layer is kept as raw text; typing and cleaning happen in the silver layer.
- Data is partitioned Hive-style by `vintage_year` so Athena can read it directly.
- Default label: flag-adjusted 24-month definition (see above), with the raw version kept for comparison.

**Modelling scope and features**
- **Model scope: non-HARP loans only.** HARP can no longer be originated, so a forward-looking model will never score one, and its risk drivers differ. Excluding it removes 30,576 loans (about 6%) and 468 defaults (about 13% of all defaults), and it is documented as an out-of-scope segment. This also removes the missing-DTI and extreme LTV and CLTV problems.
- Features dropped: `dti_missing` and `harp_indicator` (HARP proxies), `prepayment_penalty_indicator` and `interest_only_i_o_indicator` (constant), `property_valuation_method` (a proxy for time and underwriting practice), `vantage_score` (empty).
- `vintage_year` is kept only for splitting and analysis and is never a model feature.
- Engineered features: `log_orig_upb`, `two_plus_borrowers`, `first_time_buyer`, `multi_unit`.
- Candidate features: credit score, DTI, LTV, CLTV, loan amount, interest rate, mortgage insurance percentage, loan term, number of borrowers, first-time buyer, multi-unit, occupancy, loan purpose, channel, property type, state.

**Splits by origination year (non-HARP modelling dataset, 469,424 loans)**

| Split | Vintages | Loans | Defaults | Default rate |
|---|---|---|---|---|
| train | 2013-2016 | 171,769 | 776 | 0.45% |
| valid | 2017 | 48,196 | 388 | 0.81% |
| test | 2018 | 49,489 | 358 | 0.72% |
| spare | 2019 | 49,970 | 330 | 0.66% |
| replay | 2020-2022 | 150,000 | 1,218 | 0.81% |

**Models**
- Benchmark: weight-of-evidence logistic regression scorecard. Challenger: LightGBM with monotonic constraints.
- After fitting: calibration (recalibrating on the 2017 validation year because of the base-rate drift), SHAP reason codes, and a cost-based approval threshold.
- Evaluation: AUC, Gini, KS, Brier score and calibration by split, with bootstrap confidence intervals, because the test set has only 358 defaults.
- Full vintage files will be used for final training from Week 3 on SageMaker, keeping only the first 24 months of performance history per loan and downsampling non-defaults with weights.

## Next steps

1. Run the WoE scorecard (`src/train_scorecard.py`) and record the results here
2. LightGBM with monotonic constraints as the challenger
3. Calibration, SHAP reason codes, cost-based approval threshold, draft model card
4. End of Week 2: start downloading full vintage files for 2013-2018 in the background

## Open items and risks

- Confirm zero-balance codes `96` and `16`, the property valuation method codes, and how to treat modified loans, in the User Guide
- Upgrade the AWS account to the Paid plan before Week 3 (SageMaker), and check the credits balance weekly
- Thin default counts in the samples (776 in training, 358 in test): plan to retrain on full vintage files
- Investigate why the 2022 vintage has higher defaults
- Check whether the investor result (lower defaults than owner-occupiers) survives after controlling for credit score and LTV
- Test the models with and without interest rate and loan amount, which shift a lot between vintages
- Replace the manual AWS setup (bucket, Athena tables) and the long-lived CLI keys with Terraform and short-lived credentials (Week 3)