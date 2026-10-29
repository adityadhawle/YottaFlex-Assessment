
# YottaFlex Data Engineering Assessment

## 1. Project Overview

This project implements a reproducible Python and Pandas data pipeline for customer, product, and order data.

The pipeline validates source records, quarantines invalid orders, produces sales aggregates, compares baseline and optimized aggregation approaches, and generates a JSON execution report.

The implementation focuses on correctness, data quality, deterministic outputs, observability, testing, and measurable performance.

## 2. Technology Stack

- Python
- Pandas
- NumPy
- Pytest
- CSV and JSON
- Git

## 3. Architecture

```text
Synthetic Data Generator / Source CSV Files
                    |
                    v
        Input and Schema Validation
                    |
                    v
       Order Validation and DQ Rules
                    |
             +------+------+
             |             |
             v             v
       Accepted Orders   Quarantine
             |
             v
      Baseline Aggregation
             |
             v
     Optimized Aggregation
             |
             v
     Result Equivalence Check
             |
             v
      Sales Summary CSV

Pipeline Execution --> Logs and JSON Run Report
```

## 4. Project Structure

```text
YottaFlex-Assessment/
|-- data/
|   |-- customers.csv
|   |-- products.csv
|   |-- orders.csv
|-- output/
|   |-- validated_orders.csv
|   |-- quarantine.csv
|   |-- sales_summary.csv
|-- reports/
|   |-- run_report.json
|-- src/
|   |-- pipeline.py
|-- tests/
|   |-- test_pipeline.py
|-- requirements.txt
|-- README.md
```

Generated output CSVs and run reports are excluded from Git via `.gitignore`. The supplied customer, order, and product CSVs are tracked as assessment input data.

## 5. Data Dictionary

### customers.csv

| Column | Type | Rule |
|---|---|---|
| customer_id | Integer | Unique customer key; referenced by orders |
| region | String | Customer region |

Grain: One row per customer.

### products.csv

| Column | Type | Rule |
|---|---|---|
| product_id | Integer | Unique product key; referenced by orders |
| category | String | Product category |
| unit_price | Numeric | Unit selling price |

Grain: One row per product.

### orders.csv

| Column | Type | Rule |
|---|---|---|
| order_id | Integer | Unique order key |
| customer_id | Integer | Must reference an existing customer |
| product_id | Integer | Must reference an existing product |
| quantity | Numeric | Required and greater than zero |
| order_date | Date | Must be parseable as a date |
| status | String | Order status |

Grain: One row per order event in the supplied dataset.

The pipeline also adds `source_file` and `reject_reason` to quarantined records for traceability.

### Sales summary

The aggregate output is grouped by region and product category. It includes order counts and revenue derived from quantity multiplied by unit price.

## 6. Validation Rules

The pipeline checks:

- Required input files and required columns.
- Malformed CSV input and invalid dates.
- Missing order, customer, product, and quantity values.
- Duplicate order IDs; the first occurrence is retained.
- Non-positive quantities.
- Invalid customer and product references.
- Source row reconciliation against accepted and rejected records.
- Equivalence between baseline and optimized aggregation results.

Missing required columns cause a validation error. Unexpected columns currently generate a warning rather than failing the pipeline.

Rejected orders are written to `output/quarantine.csv` with a rejection reason and source filename.

## 7. Setup

Use Python with pip available.

Install dependencies:

```cmd
python -m pip install -r requirements.txt
```

Run the automated tests:

```cmd
python -m pytest tests -v
```

Run the pipeline using existing CSV files:

```cmd
python -m src.pipeline
```

Generate 100,000 reproducible synthetic orders:

```cmd
python -m src.pipeline --generate --rows 100000 --seed 42
```

Generate a smaller sample:

```cmd
python -m src.pipeline --generate --rows 1000 --seed 42
```

The generator uses a fixed random seed for reproducibility and deliberately introduces invalid records for quarantine testing.

**Warning:** Running the generator overwrites the CSV files in `data/`. Back up any custom input data first.

## 8. Outputs and Operational Report

The pipeline produces:

- `output/validated_orders.csv` — accepted orders.
- `output/quarantine.csv` — rejected orders and rejection reasons.
- `output/sales_summary.csv` — aggregated sales metrics.
- `reports/run_report.json` — run metadata, row counts, reconciliation results, timings, and status.

The report records a unique `run_id`, UTC start and end timestamps, input/output counts, rejected counts, and failure reason when execution fails.

## 9. Idempotency and Recovery

The pipeline overwrites its output files on each successful run rather than appending records.

Two consecutive executions against the same input were verified to produce byte-for-byte identical validated-order and sales-summary CSV files.

Each execution generates a new run ID. Therefore, run metadata changes even when business outputs remain identical.

The pipeline writes a failure report when an exception occurs and logs the exception. It does not currently implement transactional or atomic publication of all output files, automatic retry orchestration, or historical run-report retention. Recovery after partial failure should be performed by correcting the issue and rerunning the pipeline.

## 10. Testing

The automated test suite covers:

1. Happy-path validation and reconciliation.
2. Empty input.
3. Duplicate order IDs.
4. Missing quantity.
5. Non-positive quantity.
6. Invalid customer reference.
7. Baseline and optimized aggregation equivalence.
8. Invalid order date.
9. Invalid product reference.
10. Missing order ID.
11. Missing required schema column.
12. Unexpected schema column warning.
13. Malformed CSV input.

Latest recorded result: **13 tests passed**.

## 11. Reconciliation and Performance

A recorded local run processed 100,000 source orders.

| Metric | Result |
|---|---:|
| Source rows | 100,000 |
| Accepted rows | 99,996 |
| Rejected rows | 4 |
| Aggregate output rows | 16 |
| Source reconciliation | Passed |
| Baseline/optimized equivalence | Passed |

Two observed local performance runs:

| Run | Baseline | Optimized | Observed improvement |
|---|---:|---:|---:|
| 1 | 0.063911 s | 0.046221 s | 27.68% |
| 2 | 0.066838 s | 0.052143 s | 21.99% |

The optimization reduces repeated join and aggregation work in the analytical path. Both implementations are compared for output equivalence before the optimized result is published.

These are small-sample local timings, not a statistically rigorous benchmark. Results depend on machine load, caching, and execution conditions. More repeated runs and larger datasets are needed for stronger performance conclusions.

## 12. Design Choices and Trade-offs

- **Pandas:** Simple to run locally and appropriate for the assessment's data volumes; it is not a distributed processing engine.
- **CSV files:** Easy to inspect and reproduce without external services, but they lack transactional guarantees.
- **Quarantine:** Invalid records remain available for investigation rather than being silently discarded.
- **Baseline comparison:** Correctness is checked before accepting the optimized aggregate.
- **Deterministic generator:** A fixed seed makes test data reproducible.
- **Overwrite-based reruns:** Prevents output accumulation, but does not provide atomic multi-file publication or historical versioning.

## 13. Known Limitations and Next Steps

- Add atomic publication and stronger recovery handling for partial failures.
- Add automated end-to-end rerun and failure-recovery tests.
- Add strict configurable handling for unexpected schema changes.
- Add explicit data type and dimension-key uniqueness validation.
- Extend generated scenarios for late-arriving data and out-of-order events.
- Run repeated performance benchmarks across multiple dataset sizes.
- Add persistent historical run metadata and richer failure metrics.

## 14. Submission Notes

The solution is designed as a local, reproducible assessment project. No external credentials or services are required.

Before submission, verify the setup instructions from a clean environment, rerun the complete test suite, review generated outputs, and publish the source code and documentation in a public GitHub repository.
