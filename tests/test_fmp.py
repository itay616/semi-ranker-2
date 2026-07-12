from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from edgar_chip_screener.config import load_config
from edgar_chip_screener.fmp import FmpClient, apply_fmp_filters


@dataclass
class DummyResult:
    cik: str = "0000000001"
    tickers: str = "GOOD"
    passed: bool = True
    failed_filters: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class FakeFmpClient(FmpClient):
    def __init__(self, payloads: dict[str, Any]) -> None:
        self.payloads = payloads
        self.api_key = "fake"
        self.pause_seconds = 0

    def _json(self, endpoint: str, params: dict[str, Any]) -> Any:
        return self.payloads.get(endpoint, [])


def test_fmp_market_snapshot_extracts_values_from_mock_payloads() -> None:
    client = FakeFmpClient(
        {
            "profile-cik": [
                {
                    "symbol": "GOOD",
                    "price": 11,
                    "marketCap": 50_000_000_000,
                    "lastDiv": 0.33,
                }
            ],
            "quote": [],
            "ratios-ttm": [{"priceToBookRatioTTM": 0.8}],
            "key-metrics-ttm": [],
            "historical-price-eod/full": {
                "historical": [
                    {"date": "2026-01-01", "low": 10},
                    {"date": "2025-01-01", "low": 12},
                ]
            },
        }
    )

    snapshot = client.market_snapshot("0000000001", "GOOD")

    assert snapshot is not None
    assert snapshot.symbol == "GOOD"
    assert snapshot.market_cap == 50_000_000_000
    assert snapshot.dividend_yield is not None
    assert round(snapshot.dividend_yield, 4) == 0.03
    assert snapshot.price_to_book == 0.8
    assert snapshot.low_multiple == 1.1


def test_fmp_market_snapshot_can_get_symbol_from_cik_profile() -> None:
    client = FakeFmpClient(
        {
            "profile-cik": [{"symbol": "CIKSYM", "price": 10, "marketCap": 1}],
            "quote": [],
            "ratios-ttm": [],
            "key-metrics-ttm": [],
            "historical-price-eod/full": [],
        }
    )

    snapshot = client.market_snapshot("0000000001", "")

    assert snapshot is not None
    assert snapshot.symbol == "CIKSYM"


def test_apply_fmp_filters_marks_market_failures() -> None:
    config = load_config()
    result = DummyResult()
    client = FakeFmpClient(
        {
            "profile-cik": [{"symbol": "RICH", "price": 50, "marketCap": 250_000_000_000, "lastDiv": 0.5}],
            "quote": [],
            "ratios-ttm": [{"priceToBookRatioTTM": 3.0}],
            "key-metrics-ttm": [],
            "historical-price-eod/full": {"historical": [{"low": 10}]},
        }
    )

    apply_fmp_filters([result], config, client)

    assert not result.passed
    assert "market_cap_too_high" in result.failed_filters
    assert "low_dividend_yield" in result.failed_filters
    assert "price_to_book_too_high" in result.failed_filters
    assert "not_near_multi_year_low" in result.failed_filters
