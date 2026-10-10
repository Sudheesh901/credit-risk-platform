import sys
from pathlib import Path

import duckdb

BUCKET=sys.argv[1] if len(sys.argv) > 1 else "sudheesh-credit-risk-lake"
DATABASE="credit_risk"

TYPE_MAP = {
    "VARCHAR": "string",
    "INTEGER": "int",
    "BIGINT": "bigint",
    "SMALLINT": "smallint",
    "TINYINT": "tinyint",
    "DOUBLE": "double",
    "FLOAT": "float",
    "DATE": "date",
    "BOOLEAN": "boolean",
}

TABLES = [
    ("silver_orig", "silver/orig"),
    ("silver_labels", "silver/labels"),
]

def build_ddl(con, table, prefix):
    rows = con.execute(
        f"DESCRIBE SELECT * FROM "
        f"read_parquet('data/{prefix}/*/*.parquet', hive_partitioning=true)"
    ).fetchall()
    cols = []
    for name,dtype,*_ in rows:
        if name == "vintage_year":
            continue
        if dtype not in TYPE_MAP:
            raise ValueError(f"Unmapped type {dtype} for column {name}")
        cols.append(f"  `{name}` {TYPE_MAP[dtype]}")
    col_block = ",\n".join(cols)
    return f"""CREATE EXTERNAL TABLE IF NOT EXISTS {DATABASE}.{table} (
{col_block}
)
PARTITIONED BY (vintage_year int)
STORED AS PARQUET
LOCATION 's3://{BUCKET}/{prefix}/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.vintage_year.type'='integer',
  'projection.vintage_year.range'='1999,2030',
  'storage.location.template'='s3://{BUCKET}/{prefix}/vintage_year=${{vintage_year}}/'
);"""

def main():
    con = duckdb.connect()
    statements = [f"CREATE DATABASE IF NOT EXISTS {DATABASE};"]
    for table, prefix in TABLES:
        statements.append(build_ddl(con, table, prefix))
    out_dir = Path("infra/athena")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "silver_tables.sql"
    out_file.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
    print(f"Wrote {out_file} for bucket {BUCKET}")
    for s in statements:
        print("\n" + s.splitlines()[0])


if __name__ == "__main__":
    main()