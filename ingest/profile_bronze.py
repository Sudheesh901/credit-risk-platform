import duckdb
import pandas as pd

pd.set_option("display.width", 200)

con = duckdb.connect()
con.execute(
    "CREATE VIEW orig AS SELECT * FROM "
    "read_parquet('data/bronze/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW perf AS SELECT * FROM "
    "read_parquet('data/bronze/perf/*/*.parquet', hive_partitioning=true)"
)


def show(title, sql):
    print(f"\n=== {title} ===")
    print(con.execute(sql).df().to_string(index=False))


show(
    "Loans per vintage",
    "SELECT vintage_year, count(*) AS loans, count(DISTINCT loan_id) AS distinct_loans "
    "FROM orig GROUP BY 1 ORDER BY 1",
)

show(
    "Do performance loans exist in origination?",
    "SELECT p.vintage_year, count(DISTINCT p.loan_id) AS perf_loans, "
    "count(DISTINCT CASE WHEN o.loan_id IS NULL THEN p.loan_id END) AS not_in_orig "
    "FROM perf p LEFT JOIN orig o ON p.loan_id = o.loan_id "
    "GROUP BY 1 ORDER BY 1",
)

show(
    "Delinquency status values (dq_status)",
    "SELECT dq_status, count(*) AS row_count FROM perf GROUP BY 1 ORDER BY 2 DESC LIMIT 20",
)

show(
    "Zero balance codes (why a loan ended)",
    "SELECT zero_bal_code, count(*) AS row_count FROM perf GROUP BY 1 ORDER BY 2 DESC",
)

show(
    "Modification flag",
    "SELECT mod_flag, count(*) AS row_count FROM perf GROUP BY 1 ORDER BY 2 DESC",
)

parts = []
for col in ["fico", "dti", "ltv", "cltv", "orig_upb", "orig_rate",
            "mi_pct", "num_units", "num_borrowers", "vantage_score"]:
    parts.append(
        con.execute(f"""
            SELECT '{col}' AS col,
                   min(TRY_CAST({col} AS DOUBLE)) AS min_val,
                   max(TRY_CAST({col} AS DOUBLE)) AS max_val,
                   count(*) FILTER (WHERE {col} IS NULL) AS nulls,
                   count(*) FILTER (
                       WHERE TRY_CAST({col} AS DOUBLE) =
                             (SELECT max(TRY_CAST({col} AS DOUBLE)) FROM orig)
                   ) AS rows_at_max
            FROM orig
        """).df()
    )
print("\n=== Origination numeric columns: range and possible placeholders ===")
print(pd.concat(parts).to_string(index=False))