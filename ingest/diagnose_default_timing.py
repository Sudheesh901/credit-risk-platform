import duckdb
import pandas as pd

pd.set_option("display.width", 200)

con = duckdb.connect()
con.execute(
    "CREATE VIEW perf AS SELECT * FROM "
    "read_parquet('data/bronze/perf/*/*.parquet', hive_partitioning=true)"
)

EVENT = """(
    TRY_CAST(loan_age AS INTEGER) <= 24
    AND (
        TRY_CAST(dq_status AS INTEGER) >= 3
        OR dq_status = 'RA'
        OR zero_bal_code IN ('02', '03', '09', '15')
    )
)"""

con.execute(f"""
    CREATE TABLE events AS
    SELECT loan_id, vintage_year, period,
           borrower_assistance_plan AS bap,
           delinquency_due_to_disaster AS disaster
    FROM perf WHERE {EVENT}
""")
con.execute("""
    CREATE TABLE first_event AS
    SELECT loan_id, vintage_year, min(period) AS first_period
    FROM events GROUP BY 1, 2
""")

timing = con.execute("""
    SELECT vintage_year, substr(first_period, 1, 4) AS event_year, count(*) AS defaults
    FROM first_event GROUP BY 1, 2 ORDER BY 1, 2
""").df()
print("\n=== First default event: vintage (rows) by calendar year (columns) ===")
print(
    timing.pivot(index="vintage_year", columns="event_year", values="defaults")
    .fillna(0).astype(int).to_string()
)

flags = con.execute("""
    SELECT substr(f.first_period, 1, 4) AS event_year,
           e.bap AS borrower_assistance_plan,
           e.disaster AS disaster_flag,
           count(*) AS loans
    FROM first_event f
    JOIN events e ON e.loan_id = f.loan_id AND e.period = f.first_period
    GROUP BY 1, 2, 3 ORDER BY 1, 4 DESC
""").df()
print("\n=== Flags on the first default event, by calendar year ===")
print(flags.to_string(index=False))