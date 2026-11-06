"""Validate the cleaned cafe sales dataset.

Usage:
    python validate.py
    python validate.py --clean path/to/cleaned.csv --raw path/to/raw.csv

Each check counts "bad" rows. A FAIL means the data breaks a hard rule.
A WARN means something needs a human decision (it is not provably wrong).
The script exits with code 1 if any check FAILs, so it can be used in
automation as well as run by hand.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- rules ----
EXPECTED_COLUMNS = [
    "Transaction ID", "Item", "Quantity", "Price Per Unit", "Total Spent",
    "Payment Method", "Location", "Transaction Date", "Day of the week",
]
NUMERIC_COLUMNS = ["Quantity", "Price Per Unit", "Total Spent"]

ITEM_PRICE = {
    "Coffee": 2.0, "Cake": 3.0, "Cookie": 1.0, "Juice": 3.0,
    "Salad": 5.0, "Sandwich": 4.0, "Smoothie": 4.0, "Tea": 1.5,
}
PAYMENT_METHODS = {"Cash", "Credit Card", "Digital Wallet"}
LOCATIONS = {"In-store", "Takeaway"}
QUANTITY_RANGE = (1, 5)
MAX_TOTAL = 25.0  # 5 x 5.0 is the largest possible sale
YEAR = 2023
JUNK_STRINGS = {"ERROR", "UNKNOWN", "NAN", "NONE", "NULL", ""}

# Prices shared by two items: an Item cannot be inferred from these alone.
AMBIGUOUS_PRICES = {
    price for price in ITEM_PRICE.values()
    if sum(p == price for p in ITEM_PRICE.values()) > 1
}


# --------------------------------------------------------------- helpers ----
def result(name, bad, severity="FAIL", detail=""):
    """One check result. `bad` is the number of offending rows (0 = pass)."""
    return {"name": name, "bad": int(bad), "severity": severity, "detail": detail}


def non_null(df, *cols):
    return df.dropna(subset=list(cols))


# ---------------------------------------------------------------- checks ----
def check_structure(df):
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    extra = [c for c in df.columns if c not in EXPECTED_COLUMNS]
    out = [result("Expected columns present", len(missing),
                  detail=f"missing: {missing}" if missing else "")]
    if extra:
        out.append(result("No unexpected columns", len(extra), "WARN",
                          f"extra: {extra}"))
    return out


def check_types(df):
    bad_cols = [c for c in NUMERIC_COLUMNS
                if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]
    return [result("Numeric columns are numbers", len(bad_cols),
                   detail=f"not numeric: {bad_cols}" if bad_cols else "")]


def check_uniqueness(df):
    return [
        result("No duplicate rows", df.duplicated().sum()),
        result("No duplicate Transaction IDs", df["Transaction ID"].duplicated().sum()),
        result("Transaction ID format (TXN_<digits>)",
               (~df["Transaction ID"].astype(str).str.fullmatch(r"TXN_\d+")).sum()),
        result("Transaction ID never missing", df["Transaction ID"].isna().sum()),
    ]


def check_junk_strings(df):
    total = 0
    cols = []
    for col in df.columns:
        n = df[col].dropna().astype(str).str.strip().str.upper().isin(JUNK_STRINGS).sum()
        if n:
            total += n
            cols.append(f"{col}={n}")
    return [result("No ERROR/UNKNOWN/blank-string leftovers", total,
                   detail=", ".join(cols))]


def check_valid_values(df):
    out = []
    out.append(result("Item is a known item",
                      (~non_null(df, "Item")["Item"].isin(ITEM_PRICE)).sum()))
    out.append(result("Payment Method is an allowed value",
                      (~non_null(df, "Payment Method")["Payment Method"].isin(PAYMENT_METHODS)).sum()))
    out.append(result("Location is an allowed value",
                      (~non_null(df, "Location")["Location"].isin(LOCATIONS)).sum()))

    q = df["Quantity"].dropna()
    out.append(result("Quantity is a whole number", (q % 1 != 0).sum()))
    out.append(result(f"Quantity within {QUANTITY_RANGE[0]}-{QUANTITY_RANGE[1]}",
                      ((q < QUANTITY_RANGE[0]) | (q > QUANTITY_RANGE[1])).sum()))

    p = df["Price Per Unit"].dropna()
    out.append(result("Price Per Unit is a valid menu price",
                      (~p.isin(set(ITEM_PRICE.values()))).sum()))

    t = df["Total Spent"].dropna()
    out.append(result(f"Total Spent between 0 and {MAX_TOTAL}",
                      ((t <= 0) | (t > MAX_TOTAL)).sum()))
    return out


def check_business_rules(df):
    out = []

    both = non_null(df, "Item", "Price Per Unit")
    expected_price = both["Item"].map(ITEM_PRICE)
    out.append(result("Each Item has its fixed price",
                      (~np.isclose(expected_price, both["Price Per Unit"])).sum()))

    full = non_null(df, "Quantity", "Price Per Unit", "Total Spent")
    out.append(result("Quantity x Price = Total",
                      (~np.isclose(full["Quantity"] * full["Price Per Unit"],
                                   full["Total Spent"])).sum()))
    return out


def check_dates(df):
    parsed = pd.to_datetime(df["Transaction Date"], errors="coerce")
    has_text = df["Transaction Date"].notna()
    out = [result("Dates parse correctly", (parsed.isna() & has_text).sum())]

    valid = parsed.dropna()
    out.append(result(f"Dates fall inside {YEAR}", (valid.dt.year != YEAR).sum()))

    if "Day of the week" not in df.columns:
        return out  # already reported by the column-structure check

    mask = parsed.notna() & df["Day of the week"].notna()
    out.append(result("Weekday matches the date",
                      (parsed[mask].dt.day_name() != df.loc[mask, "Day of the week"]).sum()))

    out.append(result("Weekday present exactly when date present",
                      (parsed.notna() != df["Day of the week"].notna()).sum()))
    return out


def check_missing_report(df):
    """Informational: how many values are still missing per column."""
    counts = df.isna().sum()
    counts = counts[counts > 0]
    detail = ", ".join(f"{c}={n}" for c, n in counts.items()) or "none"
    return [result("Remaining missing values (info)", 0, "INFO", detail)]


def check_against_raw(df, raw):
    out = []
    dropped = len(raw) - len(df)
    out.append(result("Rows dropped vs raw file (info)", 0, "INFO",
                      f"raw={len(raw)}, clean={len(df)}, dropped={dropped}"))

    # Item values that were blank in the raw file but sit on an ambiguous price
    # are guesses: the price cannot tell Cake from Juice or Sandwich from Smoothie.
    merged = raw[["Transaction ID", "Item"]].merge(
        df[["Transaction ID", "Item", "Price Per Unit"]],
        on="Transaction ID", suffixes=("_raw", "_clean"))
    was_bad = (merged["Item_raw"].isna()
               | merged["Item_raw"].astype(str).str.strip().str.upper().isin(JUNK_STRINGS))
    guessed = merged[was_bad
                     & merged["Item_clean"].notna()
                     & merged["Price Per Unit"].isin(AMBIGUOUS_PRICES)]
    detail = ""
    if len(guessed):
        detail = "filled as: " + ", ".join(
            f"{k}={v}" for k, v in guessed["Item_clean"].value_counts().items())
    out.append(result("Item filled where price is ambiguous (guesses)",
                      len(guessed), "WARN", detail))
    return out


# ---------------------------------------------------------------- runner ----
def run_checks(df, raw=None):
    results = []
    # Checks that look at the raw text (types, junk strings) use df as loaded.
    for check in (check_structure, check_types, check_uniqueness, check_junk_strings):
        results.extend(check(df))

    # Numeric rules need real numbers, so coerce text to NaN first. This lets the
    # script run on messy files too, instead of crashing on strings like "ERROR".
    numeric = df.copy()
    for col in NUMERIC_COLUMNS:
        if col in numeric.columns:
            numeric[col] = pd.to_numeric(numeric[col], errors="coerce")
    for check in (check_valid_values, check_business_rules,
                  check_dates, check_missing_report):
        results.extend(check(numeric))
    if raw is not None:
        results.extend(check_against_raw(df, raw))
    return results


def print_report(results):
    width = max(len(r["name"]) for r in results)
    print(f"{'STATUS':<6}  {'CHECK':<{width}}  BAD ROWS  DETAIL")
    print("-" * (width + 30))
    for r in results:
        if r["severity"] == "INFO":
            status = "INFO"
        elif r["bad"] == 0:
            status = "PASS"
        else:
            status = r["severity"]
        print(f"{status:<6}  {r['name']:<{width}}  {r['bad']:>8}  {r['detail']}")

    fails = sum(1 for r in results if r["severity"] == "FAIL" and r["bad"] > 0)
    warns = sum(1 for r in results if r["severity"] == "WARN" and r["bad"] > 0)
    passed = sum(1 for r in results if r["severity"] in ("FAIL", "WARN") and r["bad"] == 0)
    print("-" * (width + 30))
    print(f"{passed} passed, {fails} failed, {warns} warnings")
    return fails


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean", default="data/clean/CleanedCafeSalesDataset_1.csv",
                        help="path to the cleaned CSV")
    parser.add_argument("--raw", default="data/raw/dirty_cafe_sales.csv",
                        help="path to the raw CSV (optional, enables comparison checks)")
    args = parser.parse_args()

    clean_path = Path(args.clean)
    if not clean_path.exists():
        sys.exit(f"Cleaned file not found: {clean_path}")
    df = pd.read_csv(clean_path)

    raw = None
    raw_path = Path(args.raw)
    if raw_path.exists():
        raw = pd.read_csv(raw_path)
    else:
        print(f"(raw file not found at {raw_path}; skipping comparison checks)\n")

    fails = print_report(run_checks(df, raw))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
