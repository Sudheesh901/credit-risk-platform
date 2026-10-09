import duckdb
import pandas as pd

pd.set_option("display.width",200)

con=duckdb.connect()

con.execute(
    "CREATE VIEW orig AS SELECT * FROM "
    "read_parquet('data/silver/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW labels AS SELECT * FROM "
    "read_parquet('data/silver/labels/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW perf AS SELECT * FROM "
    "read_parquet('data/bronze/perf/*/*.parquet', hive_partitioning=true)"
)

def show(title,sql):
    print(f"==={title}")
    print(con.execute(sql).df().to_string(index=False))

SHORT = (
    "SELECT loan_id FROM labels "
    "WHERE months_observed IS NULL OR months_observed < 1"
)

show(
    "A1. Loans with no observed month after age 0: null or zero?",
    f"""SELECT months_observed IS NULL AS is_null, months_observed, count(*) AS loans
        FROM labels WHERE loan_id IN ({SHORT}) GROUP BY 1, 2""",
)

show(
    "A2. Performance rows per loan for those loans",
    f"""SELECT n_rows, count(*) AS loans FROM (
            SELECT loan_id, count(*) AS n_rows FROM perf
            WHERE loan_id IN ({SHORT}) GROUP BY 1
        ) GROUP BY 1 ORDER BY 1""",
)
show(
    "A3. Zero-balance codes for those loans",
    f"""SELECT zero_bal_code, count(DISTINCT loan_id) AS loans FROM perf
        WHERE loan_id IN ({SHORT}) GROUP BY 1 ORDER BY 2 DESC""",
)

show(
    "B1. LTV values above 200 or below 1",
    """SELECT ltv, count(*) AS loans FROM orig
       WHERE ltv > 200 OR ltv < 1 GROUP BY 1 ORDER BY 2 DESC LIMIT 15""",
)
show(
    "B2. High LTV (above 105) by program and purpose",
    """SELECT harp_indicator, loan_purpose, count(*) AS loans,
              min(ltv) AS min_ltv, max(ltv) AS max_ltv
       FROM orig WHERE ltv > 105 GROUP BY 1, 2 ORDER BY 3 DESC""",
)
show(
    "B3. CLTV values above 250 or below 1",
    """SELECT cltv, count(*) AS loans FROM orig
       WHERE cltv > 250 OR cltv < 1 GROUP BY 1 ORDER BY 2 DESC LIMIT 15""",
)

show(
    "C1. First payment year far from the vintage",
    """SELECT vintage_year, year(first_payment_date) AS first_payment_year,
              count(*) AS loans
       FROM orig
       WHERE year(first_payment_date) NOT BETWEEN vintage_year - 1 AND vintage_year + 1
       GROUP BY 1, 2 ORDER BY 1, 2""",
)
show(
    "C2. Examples",
    """SELECT loan_id, vintage_year, first_payment_date, maturity_date,
              orig_term, loan_purpose, channel
       FROM orig
       WHERE year(first_payment_date) NOT BETWEEN vintage_year - 1 AND vintage_year + 1
       ORDER BY vintage_year LIMIT 10""",
)