import shutil
from pathlib import Path

import duckdb
import pandas as pd

pd.set_option("display.width", 200)

shutil.rmtree("data/silver", ignore_errors=True)
Path("data/silver").mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute(
    "CREATE VIEW orig AS SELECT * FROM "
    "read_parquet('data/bronze/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW perf AS SELECT * FROM "
    "read_parquet('data/bronze/perf/*/*.parquet', hive_partitioning=true)"
)

IN_WINDOW = "TRY_CAST(loan_age AS INTEGER) <= 24"
CREDIT_END = "zero_bal_code IN ('02', '03', '09', '15')"
SEVERE_DQ = "(TRY_CAST(dq_status AS INTEGER) >= 3 OR dq_status = 'RA')"
RELIEF = "(borrower_assistance_plan = 'F' OR delinquency_due_to_disaster = 'Y')"

# Raw label: any 90+ day delinquency, REO, or credit-event ending in the first 24 months.
RAW_EVENT = f"({IN_WINDOW} AND ({SEVERE_DQ} OR {CREDIT_END}))"

# Adjusted label: 90+ day delinquency does not count while the loan is in
# forbearance or flagged as disaster-related. Credit-event endings and REO always count.
ADJ_EVENT = f"""({IN_WINDOW} AND (
    {CREDIT_END}
    OR dq_status = 'RA'
    OR (TRY_CAST(dq_status AS INTEGER) >= 3 AND NOT COALESCE({RELIEF}, FALSE))
))"""

con.execute(f"""
    CREATE TABLE labels AS
    SELECT
        loan_id,
        vintage_year,
        max(CASE WHEN {ADJ_EVENT} THEN 1 ELSE 0 END) AS default_24m,
        max(CASE WHEN {RAW_EVENT} THEN 1 ELSE 0 END) AS default_24m_raw,
        min(CASE WHEN {ADJ_EVENT} THEN TRY_CAST(loan_age AS INTEGER) END) AS first_default_age,
        max(TRY_CAST(loan_age AS INTEGER)) AS months_observed,
        max(CASE WHEN {IN_WINDOW} AND mod_flag = 'Y' THEN 1 ELSE 0 END) AS ever_modified_24m,
        max(CASE WHEN {IN_WINDOW} AND borrower_assistance_plan = 'F'
                 THEN 1 ELSE 0 END) AS ever_forbearance_24m
    FROM perf
    GROUP BY loan_id, vintage_year
""")

con.execute("""
    CREATE TABLE silver_orig AS
    SELECT
        * EXCLUDE (vantage_score, fico, dti, ltv, cltv, orig_upb, orig_rate, mi_pct,
                   num_units, num_borrowers, orig_term, first_payment_date, maturity_date),
        CASE WHEN TRY_CAST(fico AS INTEGER) BETWEEN 300 AND 850
             THEN TRY_CAST(fico AS INTEGER) END AS fico,
        CASE WHEN TRY_CAST(dti AS DOUBLE) = 999 THEN 1 ELSE 0 END AS dti_missing,
        NULLIF(TRY_CAST(dti AS DOUBLE), 999) AS dti,
        NULLIF(TRY_CAST(ltv AS DOUBLE), 999) AS ltv,
        NULLIF(TRY_CAST(cltv AS DOUBLE), 999) AS cltv,
        TRY_CAST(orig_upb AS DOUBLE) AS orig_upb,
        TRY_CAST(orig_rate AS DOUBLE) AS orig_rate,
        TRY_CAST(mi_pct AS DOUBLE) AS mi_pct,
        TRY_CAST(num_units AS INTEGER) AS num_units,
        TRY_CAST(num_borrowers AS INTEGER) AS num_borrowers,
        TRY_CAST(orig_term AS INTEGER) AS orig_term,
        CAST(try_strptime(first_payment_date, '%Y%m') AS DATE) AS first_payment_date,
        CAST(try_strptime(maturity_date, '%Y%m') AS DATE) AS maturity_date
    FROM orig
""")

con.execute(
    "COPY silver_orig TO 'data/silver/orig' "
    "(FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (vintage_year), OVERWRITE_OR_IGNORE)"
)
con.execute(
    "COPY labels TO 'data/silver/labels' "
    "(FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (vintage_year), OVERWRITE_OR_IGNORE)"
)


def show(title, sql):
    print(f"\n=== {title} ===")
    print(con.execute(sql).df().to_string(index=False))


show(
    "Raw vs adjusted default rate by vintage (24-month window)",
    """SELECT vintage_year, count(*) AS loans,
              sum(default_24m_raw) AS raw_defaults,
              round(100.0 * avg(default_24m_raw), 2) AS raw_rate_pct,
              sum(default_24m) AS adj_defaults,
              round(100.0 * avg(default_24m), 2) AS adj_rate_pct,
              round(100.0 * avg(ever_forbearance_24m), 2) AS forbearance_pct
       FROM labels GROUP BY 1 ORDER BY 1""",
)

show(
    "Adjusted default rate by credit score band (sanity check)",
    """SELECT CASE WHEN o.fico IS NULL THEN 'missing'
                    WHEN o.fico < 680 THEN '1: below 680'
                    WHEN o.fico < 720 THEN '2: 680-719'
                    WHEN o.fico < 760 THEN '3: 720-759'
                    ELSE '4: 760+' END AS fico_band,
              count(*) AS loans, sum(l.default_24m) AS defaults,
              round(100.0 * avg(l.default_24m), 2) AS default_rate_pct
       FROM silver_orig o JOIN labels l USING (loan_id)
       GROUP BY 1 ORDER BY 1""",
)

show(
    "Missing values after cleaning",
    """SELECT count(*) AS loans,
              count(*) FILTER (WHERE fico IS NULL) AS fico_null,
              count(*) FILTER (WHERE dti IS NULL) AS dti_null,
              count(*) FILTER (WHERE ltv IS NULL) AS ltv_null,
              count(*) FILTER (WHERE cltv IS NULL) AS cltv_null
       FROM silver_orig""",
)