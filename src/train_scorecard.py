from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score,roc_curve

pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 200)

Path("report").mkdir(exist_ok=True)

NUMERIC = ["fico", "dti", "ltv", "cltv", "orig_upb", "orig_rate", "mi_pct", "orig_term"]
CATEGORICAL = [
    "occupancy", "loan_purpose", "channel", "property_type", "state",
    "two_plus_borrowers", "first_time_buyer", "multi_unit",
]
TARGET = "default_24m"

def range_label(b, edges):
    if b == -1:
        return "missing"
    if b == 0:
        return f"< {edges[0]:g}"
    if b == len(edges):
        return f">= {edges[-1]:g}"
    return f"[{edges[b - 1]:g}, {edges[b]:g})"

class WoEEncoder:
    """WoE = ln(share of defaults / share of non-defaults) per bin. Higher = riskier."""

    def __init__(self, numeric, categorical, n_bins=6, min_cat_share=0.01, smoothing=0.5):
        self.numeric = numeric
        self.categorical = categorical
        self.n_bins = n_bins
        self.min_cat_share = min_cat_share
        self.smoothing = smoothing
        self.spec = {}
        self.tables = {}

    @staticmethod
    def _bin_numeric(x, edges):
        bins = np.digitize(x, edges)
        return np.where(np.isnan(x), -1, bins)

    def _woe_table(self, bins, y):
        d = pd.DataFrame({"bin": bins, "y": y})
        g = d.groupby("bin")["y"].agg(["count", "sum"])
        k, s = len(g), self.smoothing
        bad = g["sum"].astype(float)
        good = g["count"].astype(float) - bad
        dist_bad = (bad + s) / (self.total_bad + s * k)
        dist_good = (good + s) / (self.total_good + s * k)
        woe = np.log(dist_bad / dist_good)
        return pd.DataFrame(
            {
                "loans": g["count"],
                "defaults": bad,
                "default_rate_pct": 100 * bad / g["count"],
                "woe": woe,
                "iv": (dist_bad - dist_good) * woe,
            }
        )

    def _cat_series(self, df, col):
        return df[col].fillna("MISSING").astype(str)

    def fit(self, df, y):
        y = np.asarray(y)
        self.total_bad = float(y.sum())
        self.total_good = float(len(y) - y.sum())
        for col in self.numeric:
            x = df[col].astype("float64").to_numpy()
            qs = np.nanquantile(x, np.linspace(0, 1, self.n_bins + 1)[1:-1])
            edges = np.unique(qs)
            table = self._woe_table(self._bin_numeric(x, edges), y)
            table.insert(0, "bin", [range_label(b, edges) for b in table.index])
            self.spec[col] = ("num", edges)
            self.tables[col] = table
        for col in self.categorical:
            s = self._cat_series(df, col)
            share = s.value_counts(normalize=True)
            keep = set(share[share >= self.min_cat_share].index)
            mapped = s.where(s.isin(keep), "OTHER")
            table = self._woe_table(mapped.to_numpy(), y)
            table.insert(0, "bin", table.index.astype(str))
            self.spec[col] = ("cat", keep)
            self.tables[col] = table
        return self

    def transform(self, df):
        out = {}
        for col in self.numeric:
            edges = self.spec[col][1]
            bins = self._bin_numeric(df[col].astype("float64").to_numpy(), edges)
            out[f"woe_{col}"] = (
                pd.Series(bins).map(self.tables[col]["woe"]).fillna(0.0).to_numpy()
            )
        for col in self.categorical:
            keep = self.spec[col][1]
            s = self._cat_series(df, col)
            mapped = s.where(s.isin(keep), "OTHER")
            out[f"woe_{col}"] = (
                mapped.map(self.tables[col]["woe"]).fillna(0.0).to_numpy()
            )
        return pd.DataFrame(out)

    def iv_table(self):
        rows = [(col, float(t["iv"].sum())) for col, t in self.tables.items()]
        return (
            pd.DataFrame(rows, columns=["feature", "information_value"])
            .sort_values("information_value", ascending=False)
            .reset_index(drop=True)
        )

    def bins_report(self):
        parts = []
        for col, t in self.tables.items():
            parts.append(t.reset_index(drop=True).assign(feature=col))
        return pd.concat(parts)[
            ["feature", "bin", "loans", "defaults", "default_rate_pct", "woe", "iv"]
        ]

def ks_stat(y_true, p):
    fpr, tpr, _ = roc_curve(y_true, p)
    return float(np.max(tpr - fpr))

con = duckdb.connect()

df = con.execute("SELECT * FROM read_parquet('data/model/model_dataset.parquet')").df()

names = ["train", "test", "spare", "replay"]
splits={n:df[df["split"]==n].reset_index(drop=True) for n in names}

enc = WoEEncoder(NUMERIC, CATEGORICAL).fit(splits["train"], splits["train"][TARGET].to_numpy())
X = {n: enc.transform(d) for n, d in splits.items()}
y = {n: d[TARGET].to_numpy() for n, d in splits.items()}

print("=== Information value by feature (train) ===")
print(enc.iv_table().to_string(index=False))

print("\n=== Choosing regularisation strength on the validation year ===")
best = None
for C in [0.01, 0.1, 1.0, 10.0]:
    m=LogisticRegression(C=C, max_iter=2000).fit(X["train"],y["train"])
    auc=roc_auc_score(y["valid"], m.predict_proba(X["valid"])[:, 1])
    print(f"C={C:<5} validation AUC = {auc:.4f}")
    if best is None or auc > best[0]:
        best = (auc, C, m)
model = best[2]
print(f"Chosen C = {best[1]}")

print("\n=== Coefficients (positive = riskier, as expected for WoE) ===")
print(pd.Series(model.coef_[0], index=X["train"].columns).round(3).to_string())
print(f"intercept = {model.intercept_[0]:.3f}")

rows = []
for n in names:
    p = model.predict_proba(X[n])[:, 1]
    auc = roc_auc_score(y[n], p)
    rows.append(
        {
            "split": n,
            "loans": len(y[n]),
            "defaults": int(y[n].sum()),
            "actual_pct": round(100 * y[n].mean(), 2),
            "mean_pred_pct": round(100 * p.mean(), 2),
            "auc": round(auc, 4),
            "gini": round(2 * auc - 1, 4),
            "ks": round(ks_stat(y[n], p), 4),
            "brier": round(brier_score_loss(y[n], p), 5),
        }
    )
print("\n=== Scorecard performance ===")
print(pd.DataFrame(rows).to_string(index=False))

rng = np.random.default_rng(42)
p_test = model.predict_proba(X["test"])[:, 1]
yt = y["test"]
aucs = []
for _ in range(500):
    idx = rng.integers(0, len(yt), len(yt))
    aucs.append(roc_auc_score(yt[idx], p_test[idx]))
lo, hi = np.percentile(aucs, [2.5, 97.5])
print(f"\nTest AUC 95% bootstrap interval: {lo:.4f} to {hi:.4f}")

enc.bins_report().to_csv("reports/scorecard_bins.csv", index=False)
print("\nSaved bin tables to reports/scorecard_bins.csv")