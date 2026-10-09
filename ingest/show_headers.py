import sys
from pathlib import Path

import duckdb
import pandas
import pyarrow

print("Python   :",sys.version.split()[0])
print("duckdb   :",duckdb.__version__)
print("pandas   :",pandas.__version__)
print("pyarrow  :",pyarrow.__version__)

HEADERS = Path("data/raw/headers")
for name in ["origination_data_file_header.txt", "performance_data_file_header.txt"]:
    text=(HEADERS / name).read_text(encoding="UTF-8", errors="replace").strip()
    cols=text.split("|")
    print(f"\n{name}: {len(cols)} columns")
    for i,c in enumerate(cols,start=1):
        print(f": {i<2}. {c.strip()}")

