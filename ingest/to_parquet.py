import re
import time
from pathlib import Path

import duckdb

RAW = Path("data/raw")
OUT = Path("data/bronze")
YEARS = list(range(2013, 2023))

# Short, readable names for the columns we will use most. Everything else
# gets an automatic snake_case name.
ALIASES = {
    "CLASSIC FICO": "fico",
    "FIRST PAYMENT DATE": "first_payment_date",
    "FIRST TIME HOMEBUYER INDICATOR": "first_time_homebuyer",
    "MORTGAGE INSURANCE PERCENTAGE (MI %)": "mi_pct",
    "NUMBER OF UNITS": "num_units",
    "OCCUPANCY STATUS": "occupancy",
    "ORIGINAL COMBINED LOAN-TO-VALUE (CLTV)": "cltv",
    "ORIGINAL DEBT-TO-INCOME (DTI) RATIO": "dti",
    "ORIGINAL UPB": "orig_upb",
    "ORIGINAL LOAN-TO-VALUE (LTV)": "ltv",
    "ORIGINAL INTEREST RATE": "orig_rate",
    "PROPERTY STATE": "state",
    "LOAN IDENTIFIER": "loan_id",
    "ORIGINAL LOAN TERM": "orig_term",
    "NUMBER OF BORROWERS": "num_borrowers",
    "SELLER NAME": "seller",
    "VANTAGESCORE 4.0": "vantage_score",
    "CURRENT ACTUAL UPB": "current_upb",
    "CURRENT LOAN DELINQUENCY STATUS": "dq_status",
    "LOAN AGE": "loan_age",
    "REMAINING MONTHS TO LEGAL MATURITY": "remaining_months",
    "MODIFICATION FLAG": "mod_flag",
    "ZERO BALANCE CODE": "zero_bal_code",
    "ZERO BALANCE EFFECTIVE DATE": "zero_bal_date",
    "CURRENT INTEREST RATE": "current_rate",
    "ESTIMATED LOAN-TO-VALUE (ELTV)": "eltv",
    "SERVICER NAME": "servicer",
}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def read_columns(header_file):
    text = header_file.read_text(encoding="utf-8", errors="replace").strip()
    names = [n.strip() for n in text.split("|")]
    cols = [ALIASES.get(n, slug(n)) for n in names]

    seen = {}
    for original, col in zip(names, cols):
        seen.setdefault(col, []).append(original)
    for col, originals in seen.items():
        if len(originals) > 1:
            print(f"DUPLICATE '{col}' came from: {originals}")

    counts = {}
    unique = []
    for col in cols:
        counts[col] = counts.get(col, 0) + 1
        unique.append(col if counts[col] == 1 else f"{col}_{counts[col]}")
    return unique


def convert(con, src, dest, cols):
    dest.parent.mkdir(parents=True, exist_ok=True)
    col_spec = ", ".join(f"'{c}': 'VARCHAR'" for c in cols)
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{src.as_posix()}',
                delim='|', header=false,
                columns={{{col_spec}}}, all_varchar=true)
        ) TO '{dest.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{dest.as_posix()}')"
    ).fetchone()[0]


def main():
    orig_cols = read_columns(RAW / "headers" / "origination_data_file_header.txt")
    perf_cols = read_columns(RAW / "headers" / "performance_data_file_header.txt")
    print(f"orig columns: {len(orig_cols)}, perf columns: {len(perf_cols)}")
    con = duckdb.connect()
    for year in YEARS:
        for kind, cols in (("orig", orig_cols), ("perf", perf_cols)):
            src = RAW / "samples" / f"sample_{year}" / f"sample_{kind}_{year}.txt"
            if not src.exists():
                print(f"MISSING: {src}")
                continue
            dest = OUT / kind / f"vintage_year={year}" / "data.parquet"
            t0 = time.time()
            rows = convert(con, src, dest, cols)
            mb = dest.stat().st_size / 1024**2
            print(f"{kind} {year}: {rows:,} rows -> {mb:.1f} MB ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()