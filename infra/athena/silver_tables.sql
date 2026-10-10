CREATE DATABASE IF NOT EXISTS credit_risk;

CREATE EXTERNAL TABLE IF NOT EXISTS credit_risk.silver_orig (
  `first_time_homebuyer` string,
  `metropolitan_statistical_area_msa_or_metropolitan_division` string,
  `occupancy` string,
  `channel` string,
  `prepayment_penalty_indicator` string,
  `amortization_type` string,
  `state` string,
  `property_type` string,
  `postal_code` string,
  `loan_id` string,
  `loan_purpose` string,
  `seller` string,
  `super_conforming_flag` string,
  `pre_harp_loan_sequence_number` string,
  `special_eligibility_program` string,
  `harp_indicator` string,
  `property_valuation_method` string,
  `interest_only_i_o_indicator` string,
  `fico` int,
  `dti_missing` int,
  `dti` double,
  `ltv` double,
  `cltv` double,
  `orig_upb` double,
  `orig_rate` double,
  `mi_pct` double,
  `num_units` int,
  `num_borrowers` int,
  `orig_term` int,
  `first_payment_date` date,
  `maturity_date` date
)
PARTITIONED BY (vintage_year int)
STORED AS PARQUET
LOCATION 's3://sudheesh-credit-risk-lake/silver/orig/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.vintage_year.type'='integer',
  'projection.vintage_year.range'='1999,2030',
  'storage.location.template'='s3://sudheesh-credit-risk-lake/silver/orig/vintage_year=${vintage_year}/'
);

CREATE EXTERNAL TABLE IF NOT EXISTS credit_risk.silver_labels (
  `loan_id` string,
  `default_24m` int,
  `default_24m_raw` int,
  `first_default_age` int,
  `months_observed` int,
  `ever_modified_24m` int,
  `ever_forbearance_24m` int
)
PARTITIONED BY (vintage_year int)
STORED AS PARQUET
LOCATION 's3://sudheesh-credit-risk-lake/silver/labels/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.vintage_year.type'='integer',
  'projection.vintage_year.range'='1999,2030',
  'storage.location.template'='s3://sudheesh-credit-risk-lake/silver/labels/vintage_year=${vintage_year}/'
);
