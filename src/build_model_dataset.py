from pathlib import Path
import duckdb
import pandas as pd

pd.set_option("display.width",200)

Path('data/model').mkdir(parents=True, exist_ok=True)

con=duckdb.connect()

con.execute(
"CREATE VIEW orig AS SELECT * FROM "
"read_parquet('data/silver/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW labels AS SELECT * FROM "
    "read_parquet('data/silver/labels/*/*.parquet', hive_partitioning=true)"
)
# Out-of-scope segment: HARP refinances (program closed, different risk drivers).
excluded= con.execute("""
    SELECT COUNT(*) AS loans, sum(l.default_24m) AS defaults FROM  
    orig o JOIN labels l ON o.loan_id=l.loan_id
    WHERE o.harp_indicator='Y'
""").fetchone()

print(f"Excluded HARP loans: {excluded[0]:,} loans, {int(excluded[1]):,} defaults")

# vintage_year is kept only for splitting and analysis. It must never be a feature.

con.execute("""
CREATE TABLE model_dataset AS
SELECT
    o.loan_id,
    o.vintage_year,
    CASE
        WHEN o.vintage_year BETWEEN 2013 AND 2016 THEN 'train'
        WHEN o.vintage_year = 2017 THEN 'valid'
        WHEN o.vintage_year = 2018 THEN 'test'
        WHEN o.vintage_year = 2019 THEN 'spare'
        ELSE 'replay'
    END as split,
    l.default_24m,
    o.fico,
    o.dti,
    o.ltv,
    o.cltv,
    o.orig_upb,
    ln(o.orig_upb) AS log_orig_upb,
    o.orig_rate,
    o.mi_pct,
    o.orig_term,
    CAST(o.num_borrowers >= 2 AS INTEGER) AS two_plus_borrowers,
    CAST(o.first_time_homebuyer = 'Y' AS INTEGER) AS first_time_buyer,
    CAST(o.num_units > 1 AS INTEGER) AS multi_unit,
    o.occupancy,
    o.loan_purpose,
    o.channel,
    o.property_type,
    o.state
FROM orig o
JOIN labels l ON o.loan_id=l.loan_id
WHERE COALESCE(o.harp_indicator, 'N') <> 'Y'
""")

con.execute(
"COPY model_dataset TO 'data/model/model_dataset.parquet' "
"(FORMAT PARQUET, COMPRESSION ZSTD)"
)
print("\n=== Loans, defaults and default rate by split ===")
print(
    con.execute(
        """
SELECT split,
min(vintage_year) AS first_vintage,
max(vintage_year) AS last_vintage,
count(*) AS loans,
sum(default_24m) AS defaults,
round(100.0 * avg(default_24m), 2) AS default_rate_pct
FROM model_dataset
GROUP BY 1 ORDER BY first_vintage
"""
    ).df().to_string(index=False)
)

print("\n=== Missing values in the modelling dataset ===")

print(
    con.execute(
        """
SELECT COUNT(*) AS loans,
    COUNT(*) FILTER (WHERE fico IS NULL) AS fico_NULL,
    count(*) FILTER (WHERE dti IS NULL) AS dti_null,
    count(*) FILTER (WHERE ltv IS NULL) AS ltv_null,
    count(*) FILTER (WHERE cltv IS NULL) AS cltv_null
FROM model_dataset
"""
    ).df().to_string(index=False)
)

print("\n=== Range check after excluding HARP ===")

print(
    con.execute("""
        SELECT max(ltv) AS max_ltv, max(cltv) AS max_cltv,
               min(fico) AS min_fico, max(fico) AS max_fico, max(dti) AS max_dti
        FROM model_dataset
    """).df().to_string(index=False)
)