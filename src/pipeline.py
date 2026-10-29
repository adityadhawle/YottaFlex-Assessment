
from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
REPORTS = ROOT / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOG = logging.getLogger("yottaflex")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def generate_data(n: int = 100_000, seed: int = 42):
    """Create deterministic synthetic customers, products and orders."""
    import numpy as np

    if n < 0:
        raise ValueError("n must be non-negative")

    rng = np.random.default_rng(seed)
    DATA.mkdir(parents=True, exist_ok=True)

    customer_count = max(2, n // 5)

    customers = pd.DataFrame({
        "customer_id": range(1, customer_count + 1),
        "region": rng.choice(
            ["north", "south", "east", "west"], customer_count
        ),
    })

    products = pd.DataFrame({
        "product_id": range(1, 101),
        "category": rng.choice(
            ["electronics", "home", "fashion", "books"], 100
        ),
        "unit_price": rng.integers(10, 1000, 100).astype(float),
    })

    orders = pd.DataFrame({
        "order_id": range(1, n + 1),
        "customer_id": rng.integers(1, customer_count + 1, n),
        "product_id": rng.integers(1, 101, n),
        "quantity": rng.integers(1, 6, n),
        "order_date": (
            pd.to_datetime("2026-01-01")
            + pd.to_timedelta(rng.integers(0, 270, n), unit="D")
        ),
        "status": rng.choice(
            ["completed", "pending", "cancelled"],
            n,
            p=[0.75, 0.15, 0.10],
        ),
    })

    # Intentionally create invalid records for quarantine testing.
    if n >= 10:
        orders.loc[0, "quantity"] = 0
        orders.loc[1, "customer_id"] = -1
        orders.loc[2, "quantity"] = None
        orders.loc[3, "order_id"] = orders.loc[4, "order_id"]

    customers.to_csv(DATA / "customers.csv", index=False)
    products.to_csv(DATA / "products.csv", index=False)
    orders.to_csv(DATA / "orders.csv", index=False)

    LOG.info("Generated %s order rows (seed=%s)", n, seed)


def read_inputs():
    """Read input CSVs and validate their schemas."""
    required_columns = {
        "customers.csv": {"customer_id", "region"},
        "products.csv": {"product_id", "category", "unit_price"},
        "orders.csv": {
            "order_id",
            "customer_id",
            "product_id",
            "quantity",
            "order_date",
            "status",
        },
    }

    frames = {}

    for filename, required in required_columns.items():
        path = DATA / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Required input file missing: {filename}"
            )

        try:
            frame = pd.read_csv(path)
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise ValueError(
                f"Malformed input file {filename}: {exc}"
            ) from exc

        missing = required - set(frame.columns)
        unexpected = set(frame.columns) - required

        if missing:
            raise ValueError(
                f"{filename} missing required columns: {sorted(missing)}"
            )

        if unexpected:
            LOG.warning(
                "%s contains unexpected columns: %s",
                filename,
                sorted(unexpected),
            )

        frames[filename] = frame

    customers = frames["customers.csv"]
    products = frames["products.csv"]
    orders = frames["orders.csv"].copy()

    orders["order_date"] = pd.to_datetime(
        orders["order_date"], errors="coerce"
    )

    return customers, products, orders


def validate_orders(orders, customers, products):
    """Separate accepted and rejected orders with rejection reasons."""
    df = orders.copy()
    df["source_file"] = "orders.csv"
    df["reject_reason"] = ""

    def reject(mask, reason):
        eligible = df["reject_reason"].eq("")
        df.loc[mask & eligible, "reject_reason"] = reason

    reject(df["order_id"].isna(), "missing_order_id")
    reject(df["customer_id"].isna(), "missing_customer_id")
    reject(df["product_id"].isna(), "missing_product_id")
    reject(df["quantity"].isna(), "missing_quantity")

    reject(
        df["quantity"].notna() & (df["quantity"] <= 0),
        "quantity_must_be_positive",
    )

    reject(df["order_date"].isna(), "invalid_order_date")

    reject(
        df["order_id"].duplicated(keep="first"),
        "duplicate_order_id",
    )

    valid_customer_ids = set(customers["customer_id"])
    valid_product_ids = set(products["product_id"])

    reject(
        ~df["customer_id"].isin(valid_customer_ids),
        "invalid_customer_reference",
    )
    reject(
        ~df["product_id"].isin(valid_product_ids),
        "invalid_product_reference",
    )

    rejected = df[df["reject_reason"].ne("")].copy()

    accepted = df[df["reject_reason"].eq("")].drop(
        columns=["source_file", "reject_reason"]
    ).copy()

    return accepted, rejected


def aggregate_orders(orders, customers, products, optimized=True):
    """Aggregate completed orders by region and product category."""
    if optimized:
        # Filter before joining to reduce intermediate data volume.
        filtered = orders.loc[
            orders["status"].eq("completed")
        ].copy()

        filtered = filtered.merge(
            products,
            on="product_id",
            how="inner",
            validate="many_to_one",
        )
        filtered = filtered.merge(
            customers,
            on="customer_id",
            how="inner",
            validate="many_to_one",
        )
    else:
        # Baseline joins before filtering for comparison.
        filtered = orders.merge(
            products,
            on="product_id",
            how="inner",
            validate="many_to_one",
        )
        filtered = filtered.merge(
            customers,
            on="customer_id",
            how="inner",
            validate="many_to_one",
        )
        filtered = filtered.loc[
            filtered["status"].eq("completed")
        ].copy()

    filtered["revenue"] = (
        filtered["quantity"] * filtered["unit_price"]
    )

    result = (
        filtered.groupby(
            ["region", "category"], as_index=False
        )
        .agg(
            order_count=("order_id", "nunique"),
            units_sold=("quantity", "sum"),
            revenue=("revenue", "sum"),
        )
        .sort_values(["region", "category"])
        .reset_index(drop=True)
    )

    return result


def run_pipeline():
    """Execute pipeline, validate results, and write an audit report."""
    run_id = str(uuid.uuid4())
    started = utc_now()
    start = time.perf_counter()

    DATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    try:
        customers, products, orders = read_inputs()
        accepted, rejected = validate_orders(
            orders, customers, products
        )

        # Replace outputs on each run to keep reruns reproducible.
        accepted.to_csv(
            OUTPUT / "validated_orders.csv", index=False
        )
        rejected.to_csv(
            OUTPUT / "quarantine.csv", index=False
        )

        baseline_start = time.perf_counter()
        baseline = aggregate_orders(
            accepted, customers, products, optimized=False
        )
        baseline_seconds = time.perf_counter() - baseline_start

        optimized_start = time.perf_counter()
        result = aggregate_orders(
            accepted, customers, products, optimized=True
        )
        optimized_seconds = time.perf_counter() - optimized_start

        # Do not accept an optimization that changes the result.
        pd.testing.assert_frame_equal(
            baseline,
            result,
            check_dtype=False,
            check_exact=False,
            rtol=1e-9,
            atol=1e-6,
        )

        result.to_csv(
            OUTPUT / "sales_summary.csv", index=False
        )

        report = {
            "run_id": run_id,
            "status": "success",
            "started_at": started,
            "ended_at": utc_now(),
            "source_rows": int(len(orders)),
            "accepted_rows": int(len(accepted)),
            "rejected_rows": int(len(rejected)),
            "output_rows": int(len(result)),
            "reconciliation": {
                "source_equals_accepted_plus_rejected": (
                    len(orders) == len(accepted) + len(rejected)
                ),
                "baseline_matches_optimized": True,
            },
            "performance": {
                "baseline_seconds": round(baseline_seconds, 6),
                "optimized_seconds": round(optimized_seconds, 6),
                "improvement_percent": round(
                    (
                        (baseline_seconds - optimized_seconds)
                        / baseline_seconds
                    ) * 100,
                    2,
                ) if baseline_seconds > 0 else 0,
                "note": (
                    "Single local run; timings vary by machine. "
                    "Repeat for reliable comparison."
                ),
            },
        }

        report["total_seconds"] = round(
            time.perf_counter() - start, 6
        )

        (REPORTS / "run_report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )

        LOG.info(
            "Run %s completed: %s accepted, %s rejected",
            run_id,
            len(accepted),
            len(rejected),
        )

        print(json.dumps(report, indent=2))
        return report

    except Exception as exc:
        failure = {
            "run_id": run_id,
            "status": "failed",
            "started_at": started,
            "ended_at": utc_now(),
            "failure_reason": str(exc),
        }

        (REPORTS / "run_report.json").write_text(
            json.dumps(failure, indent=2),
            encoding="utf-8",
        )

        LOG.exception("Pipeline failed")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="YottaFlex analytical pipeline"
    )
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if args.generate:
        generate_data(args.rows, args.seed)

    run_pipeline()


if __name__ == "__main__":
    main()
