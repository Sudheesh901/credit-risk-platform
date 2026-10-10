##Before modelling, we need to look at the features: how HARP loans behave across vintages, where to cap extreme values, and which categories carry signal.

import duckdb
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 200)

con = duckdb.connect()
con.execute(
    "CREATE VIEW orig AS SELECT * FROM "
    "read_parquet('data/silver/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW labels AS SELECT * FROM "
    "read_parquet('data/silver/labels/*/*.parquet', hive_partitioning=true)"
)


def show(title, df):
    print(f"\n=== {title} ===")
    print(df.to_string(index=False))


show(
    "HARP vs non-HARP loans by vintage",
    con.execute("""
        SELECT o.vintage_year,
               COALESCE(o.harp_indicator, 'N') AS harp,
               count(*) AS loans,
               sum(l.default_24m) AS defaults,
               round(100.0 * avg(l.default_24m), 2) AS default_rate_pct,
               round(avg(o.ltv), 1) AS avg_ltv
        FROM orig o JOIN labels l USING (loan_id)
        GROUP BY 1, 2 ORDER BY 1, 2
    """).df(),
)

numeric_cols = ["fico", "dti", "ltv", "cltv", "orig_upb", "orig_rate", "mi_pct"]
parts = []
for col in numeric_cols:
    parts.append(
        con.execute(f"""
            SELECT '{col}' AS feature,
                   min({col}) AS min_val,
                   quantile_cont({col}, 0.01) AS p01,
                   quantile_cont({col}, 0.50) AS p50,
                   quantile_cont({col}, 0.99) AS p99,
                   max({col}) AS max_val
            FROM orig
        """).df()
    )
show("Numeric features: range and percentiles", pd.concat(parts))

cat_cols = [
    "occupancy", "loan_purpose", "channel", "first_time_homebuyer",
    "property_type", "num_borrowers", "num_units", "dti_missing",
    "prepayment_penalty_indicator", "interest_only_i_o_indicator",
    "property_valuation_method", "harp_indicator",
]
parts = []
for col in cat_cols:
    parts.append(
        con.execute(f"""
            SELECT '{col}' AS feature, CAST(o.{col} AS VARCHAR) AS value,
                   count(*) AS loans, sum(l.default_24m) AS defaults,
                   round(100.0 * avg(l.default_24m), 2) AS default_rate_pct
            FROM orig o JOIN labels l USING (loan_id)
            GROUP BY 1, 2 HAVING count(*) >= 500
            ORDER BY loans DESC
        """).df()
    )
show("Default rate by category (groups with at least 500 loans)", pd.concat(parts))