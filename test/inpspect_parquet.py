from pathlib import Path
import duckdb

SILVER_DIR=Path("data/silver")

#find all Parquet files recursively
parquet_files = list(SILVER_DIR.rglob("*.parquet"))

print(f"Total Parquet files found: {len(parquet_files)}")

# Display the first 20 file paths
for file in parquet_files[:20]:
    print(file)

# Stop if no Parquet files were found
if not parquet_files:
    raise FileNotFoundError(
        f"No Parquet files found under {SILVER_DIR.resolve()}"
    )
# 5. Inspect the first Parquet file
file_path = parquet_files[0].as_posix()
print(f"\nInspecting: {file_path}")

# 6. Connect to DuckDB
con = duckdb.connect()

# 7. Show column names and data types
schema = con.execute(
    "DESCRIBE SELECT * FROM read_parquet(?)",
    [file_path],
).df()

print("\n--- Schema ---")
print(schema.to_string(index=False))

# 8. Display the first 5 rows
sample = con.execute(
    "SELECT * FROM read_parquet(?) LIMIT 5",
    [file_path],
).df()

print("\n--- First 5 rows ---")
print(sample.to_string(index=False))

# 9. Display row count
row_count = con.execute(
    "SELECT COUNT(*) FROM read_parquet(?)",
    [file_path],
).fetchone()[0]

print(f"\nTotal rows in this file: {row_count}")

con.close()


for folder_name in ["orig", "labels"]:
    folder = SILVER_DIR / folder_name

    files = list(folder.rglob("*.parquet"))

    print(f"\n{'=' * 50}")
    print(f"Folder: {folder_name}")
    print(f"Parquet files: {len(files)}")

    if files:
        file_path = files[0].as_posix()

        result = duckdb.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [file_path],
        ).df()

        print("\nSchema:")
        print(result.to_string(index=False))

        print("\nSample records:")
        print(
            duckdb.execute(
                "SELECT * FROM read_parquet(?) LIMIT 3",
                [file_path],
            ).df().to_string(index=False)
        )
