
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import aggregate_orders, validate_orders


@pytest.fixture
def dimensions():
    customers = pd.DataFrame({
        "customer_id": [1, 2],
        "region": ["north", "south"],
    })
    products = pd.DataFrame({
        "product_id": [10, 20],
        "category": ["books", "home"],
        "unit_price": [100.0, 50.0],
    })
    return customers, products


@pytest.fixture
def valid_orders():
    return pd.DataFrame({
        "order_id": [101, 102, 103],
        "customer_id": [1, 2, 1],
        "product_id": [10, 20, 10],
        "quantity": [2, 3, 1],
        "order_date": pd.to_datetime([
            "2026-01-01", "2026-01-02", "2026-01-03"
        ]),
        "status": ["completed", "completed", "pending"],
    })


def test_happy_path_reconciles(valid_orders, dimensions):
    customers, products = dimensions
    accepted, rejected = validate_orders(valid_orders, customers, products)

    assert len(accepted) == 3
    assert len(rejected) == 0
    assert len(valid_orders) == len(accepted) + len(rejected)


def test_empty_input(valid_orders, dimensions):
    customers, products = dimensions
    empty = valid_orders.iloc[0:0].copy()

    accepted, rejected = validate_orders(empty, customers, products)

    assert accepted.empty
    assert rejected.empty
    result = aggregate_orders(accepted, customers, products)
    assert result.empty


def test_duplicate_order_id_is_rejected(valid_orders, dimensions):
    customers, products = dimensions
    duplicate = pd.concat(
        [valid_orders, valid_orders.iloc[[0]]],
        ignore_index=True,
    )

    accepted, rejected = validate_orders(duplicate, customers, products)

    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reason"] == "duplicate_order_id"
    assert len(accepted) == 3


def test_null_quantity_is_rejected(valid_orders, dimensions):
    customers, products = dimensions
    data = valid_orders.copy()
    data.loc[0, "quantity"] = None

    accepted, rejected = validate_orders(data, customers, products)

    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reason"] == "missing_quantity"


def test_non_positive_quantity_is_rejected(valid_orders, dimensions):
    customers, products = dimensions
    data = valid_orders.copy()
    data.loc[0, "quantity"] = 0

    accepted, rejected = validate_orders(data, customers, products)

    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reason"] == "quantity_must_be_positive"


def test_invalid_customer_reference_is_rejected(valid_orders, dimensions):
    customers, products = dimensions
    data = valid_orders.copy()
    data.loc[0, "customer_id"] = 999

    accepted, rejected = validate_orders(data, customers, products)

    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reason"] == "invalid_customer_reference"


def test_aggregation_matches_baseline(valid_orders, dimensions):
    customers, products = dimensions

    baseline = aggregate_orders(
        valid_orders, customers, products, optimized=False
    )
    optimized = aggregate_orders(
        valid_orders, customers, products, optimized=True
    )

    pd.testing.assert_frame_equal(
        baseline, optimized, check_dtype=False
    )
    assert optimized["order_count"].sum() == 2
    assert optimized["revenue"].sum() == 350.0


def test_invalid_order_date_is_rejected(dimensions, valid_orders):
    customers, products = dimensions
    valid_orders.loc[0, "order_date"] = pd.NaT

    accepted, rejected = validate_orders(
        valid_orders, customers, products
    )

    assert len(accepted) == 2
    assert len(rejected) == 1
    assert rejected.iloc[0]["reject_reason"] == "invalid_order_date"


