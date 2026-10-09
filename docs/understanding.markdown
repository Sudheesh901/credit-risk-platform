## Convert the raw text files to Parquet
> Parquet is a compact, fast file format that Athena and every cloud tool understands. This step produces what data engineers call the bronze layer: the raw data, stored exactly as received (all text), with proper column names attached. Typing and cleaning come in a later step. Keeping a faithful raw copy means you can always re-derive everything.

> The script uses DuckDB, which streams the large files from disk instead of loading 450 MB into memory at once. It writes into vintage_year=2013/-style folders, which is the layout Athena expects.