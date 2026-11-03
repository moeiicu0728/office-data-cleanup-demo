# Downloadable configurable CSV/XLSX cleanup example

[Download the source archive](advanced-cleanup-source.zip). Extract it and run the commands below from the `advanced-cleanup` directory. The archive contains the code, dependency list, existing tests and synthetic CSV/XLSX fixtures.

This is AI-assisted original demonstration code, not a client case study, an n8n client workflow or evidence of earnings. Input mappings and business rules must be agreed separately for any real project.

Independent package check on 2026-11-03: extracted the exact archive into a new directory, ran all 15 existing unit tests successfully, and ran the documented demo command. Its 14 synthetic rows reconciled as 4 clean, 8 exception, 1 duplicate and 1 blank; parseable amounts reconciled with zero difference. CPython 3.12.14 / openpyxl 3.1.5.

Archive SHA-256: `43ac2d2dee85d9d81b531941599fe47ac77cbbd4e8fdebf34ea0a6127ad2401b`.

---

# Configurable CSV/XLSX cleanup CLI

A local Python command-line tool for merging and cleaning tabular files according to explicit JSON rules. **All bundled records are synthetic.** This is a reproducible code example, not a customer case study.

## Run

Use Python 3.10 or newer. In this directory, install the dependency with the same interpreter used to run the tool:

```sh
python --version
python -m pip install --index-url https://pypi.org/simple -r requirements.txt
python tidy_data.py --config examples/rules.json --input cn_csv=examples/data/synthetic_orders.csv --input en_xlsx=examples/data/synthetic_orders.xlsx --out result
python -m unittest -v
```

Replace `python` with your Python 3.10+ interpreter command if necessary. The output directory must not already exist. The existing test suite was verified with CPython 3.12.14 and openpyxl 3.1.5.

## Behavior

- Read multiple CSV/XLSX files. Each input names a declared source profile; column mappings, CSV encoding/delimiter and XLSX sheets are explicit.
- Normalize text, complete dates and Decimal amounts only according to the supplied rules. Do not infer column names, missing dates, leading zeros, currencies or business meaning.
- Use the configured primary key. Keep one copy of identical valid normalized records; isolate every record with the same key when business fields conflict. Invalid records remain traceable.
- Track source file identifiers, SHA-256 hashes, sheet names, record numbers and physical row ranges, including multiline CSV fields.
- Reconcile every input record into clean, exception, duplicate or explicitly skipped blank rows. Reconcile parseable original amounts across those categories; count unavailable amounts separately.
- Reject XLSX formula rows without executing formulas or trusting cached values. Write formula-like source strings as literal XLSX text. CSV safety is an explicit `excel_safe` or `raw` choice, with export transformations recorded in the audit.
- Open original inputs read-only, verify their hashes again after export, and refuse to overwrite an existing output directory.

The example rules use one record per order ID. A different data grain requires a deliberately chosen key, such as order ID plus line ID. Amount aggregation is mechanical and does not establish a sales, cash-receipt or net-income definition.

## Outputs

The run produces `report.xlsx`, six CSV files (`clean`, `exceptions`, `duplicates`, `ledger`, `raw_records`, `group_summary`), `audit.json` and `rules_used.json`. The report is a static snapshot; rerun into a new directory after changing inputs or rules.

The audit preserves original and normalized records, source locations, reconciliation totals and export notes. Long audit JSON cells can be inspected through Excel's formula bar or the companion CSV/JSON. Values beyond Excel's safe numeric precision are stored as text with an audit entry. Original source files are retained.

For the bundled synthetic fixtures:

| Record disposition | Count |
| --- | ---: |
| Clean | 4 |
| Exception | 8 |
| Duplicate | 1 |
| Skipped blank | 1 |
| Total | 14 |

The parseable synthetic amount reconciles as `2649.20 = 1292.30 + 156.90 + 1200.00 + 0.00`, with zero difference. Three records have unavailable or missing amounts and are not silently filled with zero.

## Configuration and tests

Start from `examples/rules.json`. It declares canonical columns and types, source-to-target column mappings, complete date formats, decimal precision and separators, allowed values, primary keys, amount totals, grouping and blank-row behavior. Reuse a source profile for multiple files by repeating `--input profile=file`. `make_demo.py --out new-fixture-directory` reproduces the existing synthetic fixtures without overwriting a directory.

The existing 15 unittest cases cover cross-file merging, conflicts and duplicates; formula rejection and literal text exports; CSV safety modes; decimals, zero and negative amounts; ambiguous/incomplete dates; numeric identifiers; multiline CSV provenance; native Excel time values; long strings and XML control characters; input hashes; structure errors; row limits and overwrite protection. Tests create temporary synthetic inputs only.

Default limits are 100,000 records across all inputs, 256 columns and 50 MiB per source file. Limits can be explicitly configured. Unsupported source structure stops the batch; invalid values are isolated. No automatic column detection, XLS/XLSM, OCR, macro execution or formula calculation is included.
