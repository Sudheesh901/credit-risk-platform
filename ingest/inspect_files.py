from pathlib import Path

RAW = Path("data/raw")
Max=300

def peek(path, n):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for i,line in enumerate(f):
            if i>=n:
                break
            print(" ",line.rstrip("\n")[:Max])

def listing(folder, unit, div):
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    for p in files:
        print(f"  {p.relative_to(RAW)}  ({p.stat().st_size / div:.1f} {unit})")
    return files

print("=== HEADERS ===")
header_files= listing(RAW / "headers", "KB", 1024)
for p in header_files:
    if p.suffix.lower() in {".csv", ".txt"}:
        print(f"\n-- first 3 lines of {p.name}")
        peek(p, 3)
print("\n=== SAMPLES ===")
sample_files = listing(RAW / "samples", "MB", 1024**2)
shown = 0
for p in sample_files:
    if p.suffix.lower() == ".txt" and shown < 4:
        print(f"\n-- first 2 lines of {p.name}")
        peek(p, 2)
        shown += 1
