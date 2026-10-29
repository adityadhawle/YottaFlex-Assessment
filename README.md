# YottaFlex Data Engineering Assessment

## Project Overview

A Python and Pandas data pipeline that processes customer, product, and order data. It validates records, separates accepted and rejected orders, generates sales aggregates, and produces a JSON run report.

## Tech Stack

- Python
- Pandas
- Pytest
- CSV and JSON
- Git

## Project Structure

```text
YottaFlex-Assessment/
|-- data/
|   |-- customers.csv
|   |-- orders.csv
|   |-- products.csv
|-- output/
|-- reports/
|-- src/
|   |-- pipeline.py
|-- tests/
|   |-- test_pipeline.py
|-- requirements.txt
|-- README.md
```

## Pipeline Features

- Reads customer, product, and order CSV files.
- Validates required columns and input records.
- Rejects records with missing identifiers, invalid dates, missing or non-positive quantities, duplicate order IDs, and invalid customer or product references.
- Separates accepted and rejected records with rejection reasons.
- Generates sales summary outputs.
- Compares baseline and optimized aggregation results.
- Checks source-to-output reconciliation.
- Generates a JSON run report containing row counts, reconciliation status, and execution timings.
- Supports deterministic synthetic data generation.

## How to Run

Install dependencies:

```cmd
python -m pip install -r requirements.txt
```

Run the pipeline:

```cmd
python src\pipeline.py
```

Run tests:

```cmd
python -m pytest tests -v
```

## Outputs

Generated CSV files are stored in the `output/` directory. The run report is stored at `reports/run_report.json`.

## Validation and Testing

The test suite covers successful reconciliation, empty input, duplicate order IDs, missing quantities, non-positive quantities, invalid customer references, invalid order dates, and aggregation equivalence.

## Sample Execution Results

One local run processed 100,000 source rows:

| Metric | Result |
|---|---:|
| Source rows | 100,000 |
| Accepted rows | 99,996 |
| Rejected rows | 4 |
| Aggregate output rows | 16 |
| Source reconciliation | Passed |
| Baseline/optimized equivalence | Passed |
| Tests | 8 passed |

The optimized aggregation was approximately 21% faster in this single run. This is a preliminary measurement; timings vary by machine, and repeated runs are needed for a reliable benchmark.

## Notes

This assessment uses local CSV files. Performance figures are from a local execution and are not a production benchmark.