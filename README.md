# Cafe Sales Data Cleaning

Cleaning a deliberately messy 10,000-row cafe sales dataset with Python and pandas. The project covers finding what's broken, standardizing missing values, fixing data types, recovering missing values from rules hidden in the data, and validating the result.

## Goal

Turn a raw, unreliable sales export into a dataset that can be trusted for analysis (best-selling items, revenue over time, in-store vs takeaway) without silently inventing values.

## Files

| File | Description |
|---|---|
| `dirty_cafe_sales.csv` | Raw input: 10,000 rows, 8 columns |
| `CleanedCafeSalesDataset_1.csv` | Cleaned output: 9,994 rows, 9 columns (adds `Day of the week`) |

Columns: `Transaction ID`, `Item`, `Quantity`, `Price Per Unit`, `Total Spent`, `Payment Method`, `Location`, `Transaction Date`.

Source: the public "Dirty Cafe Sales" practice dataset (Kaggle). `TODO: add the exact link`.

## What was wrong with the raw data

1. **Numeric columns were stored as text**, because the strings `ERROR` and `UNKNOWN` were mixed in with the numbers.
2. **Three different ways of saying "missing":** blank cells, `ERROR` and `UNKNOWN`. Only blanks were treated as missing.
3. **Unparseable dates**, for the same reason.
4. **Many gaps.** Unusable values per column (blank + `ERROR` + `UNKNOWN`):

| Column | Unusable in raw data | Missing in cleaned data |
|---|---:|---:|
| Transaction ID | 0 | 0 |
| Item | 969 | 0 (see Known issues) |
| Quantity | 479 | 20 |
| Price Per Unit | 533 | 0 |
| Total Spent | 502 | 20 |
| Payment Method | 3,178 | 3,175 |
| Location | 3,961 | 3,958 |
| Transaction Date | 460 | 460 |

There were no duplicate rows and every Transaction ID was unique, in both the raw and cleaned files.

## Cleaning process

### 1. Inspect before changing anything
Checked column types, missing counts, duplicates, and the unique values of every categorical column to understand the mess before fixing it.

### 2. Standardize "missing"
Converted `ERROR` and `UNKNOWN` into real missing values, so every kind of "unknown" is treated the same way.

### 3. Fix data types
- Quantity, Price Per Unit and Total Spent converted to numbers.
- Transaction Date converted to dates (range 2023-01-01 to 2023-12-31).
- Added a `Day of the week` column derived from the date.

### 4. Find the rules hidden in the data
Before filling anything, I checked what relationships the data obeys:

- Each item has one fixed price: Coffee 2.0, Cake 3.0, Cookie 1.0, Juice 3.0, Salad 5.0, Sandwich 4.0, Smoothie 4.0, Tea 1.5.
- Quantity x Price Per Unit = Total Spent on every complete row of the raw data.
- The weekday matches the date on every row that has a date.

Important limit: **Cake and Juice both cost 3.0, and Sandwich and Smoothie both cost 4.0**, so a price alone cannot identify the item for those four. Only prices 1.0 (Cookie), 1.5 (Tea), 2.0 (Coffee) and 5.0 (Salad) point to a single item.

### 5. Recover missing values
Used the rules above to recover Price Per Unit, Quantity and Total Spent where the other fields made it possible, and Item where the price pointed to a single item. `TODO: describe the exact method and order you used.`

### 6. Handle what can't be recovered
- **Payment Method (3,175 missing) and Location (3,958 missing):** nothing else in the row implies them, and filling with the most common value would invent data, so they stay missing.
- **Transaction Date (460 missing):** unrecoverable. Rows are kept for revenue totals and excluded only from time-based analysis.
- **6 rows were dropped** because too many core fields were missing at once to recover anything (for example, Item, Price and Total all unknown). Their IDs: `TXN_3611851`, `TXN_7524977`, `TXN_7376255`, `TXN_9646000`, `TXN_1082717`, `TXN_1208561`.
- **20 rows** still have Quantity and Total Spent both missing (the price is known, but neither can be calculated).

### 7. Validate and fix
Validation after the first cleaning pass found 64 rows where Quantity x Price did not equal Total. All were Salad rows with a price of 3.0 instead of 5.0, which also caused a Quantity of 1.667. I corrected those prices (66 Price Per Unit values changed in total) and re-ran every check.

Checks on the final file:

| Check | Result |
|---|---|
| Duplicate rows / duplicate Transaction IDs | 0 / 0 |
| Leftover `ERROR`/`UNKNOWN` strings | 0 |
| Dates that fail to parse | 0 |
| Weekday does not match date | 0 |
| Non-whole-number quantities | 0 |
| Quantity x Price = Total | 0 failures out of 9,974 rows |
| Item agrees with its fixed price | 0 mismatches |
| Date range | 2023-01-01 to 2023-12-31 |

## Known issues

1. **Item values for ambiguous prices were guessed.** Of 963 recovered Item values, 474 had a price of 3.0 or 4.0, which cannot identify a single item. Every one of those 474 was assigned **Juice (247) or Smoothie (227)**, and none to Cake or Sandwich. These guesses pass every validation check because they are consistent with the price, but they are wrong in roughly half of cases. They inflate Juice and Smoothie counts and understate Cake and Sandwich, so per-item analysis is unreliable. `TODO: set these 474 to missing, or document why keeping the guess is acceptable, then update this section.`
2. **Payment Method, Location and Date** are permanently incomplete, so any analysis using them covers only part of the data.
3. The dataset is synthetic practice data, so results should not be treated as real business findings.

## Results

| Measure | Raw | Cleaned |
|---|---:|---:|
| Rows | 10,000 | 9,994 |
| Numeric columns stored as numbers | 0 of 3 | 3 of 3 |
| `ERROR`/`UNKNOWN` strings | thousands | 0 |
| Rows with all four core fields (Item, Quantity, Price, Total) | n/a | 9,974 |
| Rows failing Quantity x Price = Total | n/a | 0 |
| Item values that are guesses | n/a | 474 |

## What I learned
`TODO: write 2-3 honest lines in your own words. For example: recovering values is only half the job. Validation caught wrong prices that looked fine, and it also showed that some guesses can pass every check and still be wrong.`

## How to run

```
pip install pandas
python clean_cafe_sales.py
```

`TODO: rename to match your script. It should read dirty_cafe_sales.csv and write the cleaned file without touching the raw data.`

## Tools
Python 3, pandas.

## Possible next steps
- Resolve the 474 guessed Item values, then update the Results table.
- Answer business questions with the cleaned data: best-selling item, revenue by month, in-store vs takeaway.
- Repeat the same queries in SQL (SQLite) and confirm the results match pandas.
