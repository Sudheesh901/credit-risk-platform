import sys

import duckdb

EXPECTED_VINTAGES = list(range(2013, 2023))
LOANS_PER_VINTAGE = 50_000  # sample files; change when using full vintages

con = duckdb.connect()
con.execute(
    "CREATE VIEW orig AS SELECT * FROM "
    "read_parquet('data/silver/orig/*/*.parquet', hive_partitioning=true)"
)
con.execute(
    "CREATE VIEW labels AS SELECT * FROM "
    "read_parquet('data/silver/labels/*/*.parquet', hive_partitioning=true)"
)

results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))


def scalar(sql):
    return con.execute(sql).fetchone()[0]


total_loans = scalar("SELECT count(*) FROM orig")

# 1. Completeness and keys
counts = dict(con.execute("SELECT vintage_year, count(*) FROM orig GROUP BY 1").fetchall())
check(
    "every vintage present with the expected loan count",
    sorted(counts) == EXPECTED_VINTAGES
    and all(v == LOANS_PER_VINTAGE for v in counts.values()),
    f"{len(counts)} vintages",
)
dupes = scalar("SELECT count(*) - count(DISTINCT loan_id) FROM orig")
check("loan_id is unique", dupes == 0, f"{dupes} duplicates")

missing = scalar("SELECT count(*) FROM orig o ANTI JOIN labels l USING (loan_id)")
extra = scalar("SELECT count(*) FROM labels l ANTI JOIN orig o USING (loan_id)")
check(
    "origination and labels contain the same loans",
    missing == 0 and extra == 0,
    f"{missing} without labels, {extra} labels without loans",
)

# 2. Label integrity
bad_label = scalar(
    "SELECT count(*) FROM labels WHERE default_24m IS NULL OR default_24m NOT IN (0, 1)"
)
check("default_24m is 0 or 1 with no nulls", bad_label == 0, f"{bad_label} bad rows")
adj_gt_raw = scalar("SELECT count(*) FROM labels WHERE default_24m > default_24m_raw")
check("adjusted label never exceeds raw label", adj_gt_raw == 0, f"{adj_gt_raw} rows")

null_obs = scalar("SELECT count(*) FROM labels WHERE months_observed IS NULL")
check("months_observed is never null", null_obs == 0, f"{null_obs} loans")
month0 = scalar("SELECT count(*) FROM labels WHERE months_observed = 0")
check(
    "loans with only a month-0 record are rare (below 0.1%)",
    month0 / total_loans < 0.001,
    f"{month0} loans, {month0 / total_loans:.3%}",
)

# 3. Value ranges (placeholders were already turned into NULL).
# HARP refinances had no LTV cap, so they are checked separately.
NOT_HARP = "COALESCE(harp_indicator, 'N') <> 'Y'"
range_rules = {
    "fico within 300-850": "fico IS NOT NULL AND (fico < 300 OR fico > 850)",
    "dti within 0-100": "dti IS NOT NULL AND (dti < 0 OR dti > 100)",
    "ltv within 1-105 for non-HARP loans": f"{NOT_HARP} AND ltv IS NOT NULL AND (ltv < 1 OR ltv > 105)",
    "ltv within 1-600 for HARP loans": "harp_indicator = 'Y' AND ltv IS NOT NULL AND (ltv < 1 OR ltv > 600)",
    "cltv within 1-200 for non-HARP loans": f"{NOT_HARP} AND cltv IS NOT NULL AND (cltv < 1 OR cltv > 200)",
    "orig_rate within 0-15": "orig_rate IS NULL OR orig_rate < 0 OR orig_rate > 15",
    "orig_upb is positive": "orig_upb IS NULL OR orig_upb <= 0",
    "num_units within 1-4": "num_units IS NULL OR num_units < 1 OR num_units > 4",
    "num_borrowers is at least 1": "num_borrowers IS NULL OR num_borrowers < 1",
}
for name, violation in range_rules.items():
    bad = scalar(f"SELECT count(*) FROM orig WHERE {violation}")
    check(name, bad == 0, f"{bad} violations")
harp_cltv_out = scalar(
    "SELECT count(*) FROM orig WHERE harp_indicator = 'Y' "
    "AND cltv IS NOT NULL AND (cltv < 1 OR cltv > 700)"
)
harp_cltv_max = scalar("SELECT max(cltv) FROM orig WHERE harp_indicator = 'Y'")
check(
    "cltv for HARP loans: at most 5 loans outside 1-700",
    harp_cltv_out <= 5,
    f"{harp_cltv_out} loans, max cltv {harp_cltv_max:.0f}",
)

# 4. Dates
bad_dates = scalar(
    "SELECT count(*) FROM orig WHERE first_payment_date IS NULL OR maturity_date IS NULL "
    "OR maturity_date <= first_payment_date"
)
check("maturity falls after first payment", bad_dates == 0, f"{bad_dates} loans")
off_vintage = scalar(
    "SELECT count(*) FROM orig WHERE year(first_payment_date) "
    "NOT BETWEEN vintage_year - 1 AND vintage_year + 1"
)
check(
    "first payment year within a year of the vintage (outliers below 0.05%)",
    off_vintage / total_loans < 0.0005,
    f"{off_vintage} loans, {off_vintage / total_loans:.3%}",
)

# 5. Missing-value rates
for col, limit in [("fico", 0.01), ("dti", 0.10), ("ltv", 0.001), ("cltv", 0.001)]:
    rate = scalar(f"SELECT avg(({col} IS NULL)::INT) FROM orig")
    check(f"{col} missing rate below {limit:.1%}", rate < limit, f"{rate:.2%}")

# 6. Label plausibility
lo, hi = con.execute(
    "SELECT min(r), max(r) FROM "
    "(SELECT 100.0 * avg(default_24m) AS r FROM labels GROUP BY vintage_year)"
).fetchone()
check(
    "adjusted default rate per vintage within 0.1%-3.0%",
    0.1 <= lo and hi <= 3.0,
    f"min {lo:.2f}%, max {hi:.2f}%",
)

rates = [
    r
    for (r,) in con.execute("""
        SELECT 100.0 * avg(default_24m) FROM (
            SELECT CASE WHEN o.fico < 680 THEN 1 WHEN o.fico < 720 THEN 2
                        WHEN o.fico < 760 THEN 3 ELSE 4 END AS band,
                   l.default_24m
            FROM orig o JOIN labels l USING (loan_id)
            WHERE o.fico IS NOT NULL
        ) GROUP BY band ORDER BY band
    """).fetchall()
]
check(
    "default rate falls as credit score band rises",
    all(rates[i] > rates[i + 1] for i in range(len(rates) - 1)),
    " > ".join(f"{r:.2f}%" for r in rates),
)

passed = sum(results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)