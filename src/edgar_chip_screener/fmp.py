from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode
import json
from urllib.error import HTTPError
from urllib.request import urlopen

from .config import ScreenerConfig


FMP_BASE_URL = "https://financialmodelingprep.com/stable"


@dataclass(frozen=True)
class FmpMarketSnapshot:
    symbol: str
    market_cap: float | None = None
    dividend_yield: float | None = None
    price_to_book: float | None = None
    current_price: float | None = None
    multi_year_low: float | None = None

    @property
    def low_multiple(self) -> float | None:
        if not self.current_price or not self.multi_year_low or self.multi_year_low <= 0:
            return None
        return self.current_price / self.multi_year_low


class FmpClient:
    def __init__(self, api_key: str | None = None, pause_seconds: float = 0.2) -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        if not self.api_key:
            raise ValueError("FMP API key is required. Pass --fmp-api-key or set FMP_API_KEY.")
        self.pause_seconds = pause_seconds
        self.plan_limited_endpoints: set[str] = set()

    def market_snapshot(self, cik: str, tickers: str, years: int = 5) -> FmpMarketSnapshot | None:
        profile_by_cik = self._first_json("profile-cik", {"cik": cik.lstrip("0")})
        symbol = str(profile_by_cik.get("symbol") or _first_symbol(tickers))
        if not symbol:
            return None

        profile = profile_by_cik or self._first_json(
            "profile",
            {"symbol": symbol},
        )
        quote = self._first_json("quote", {"symbol": symbol})
        ratios = self._first_json("ratios-ttm", {"symbol": symbol})
        key_metrics = self._first_json("key-metrics-ttm", {"symbol": symbol})
        history = self._json(
            "historical-price-eod/full",
            {"symbol": symbol, "from": _years_ago(years), "to": date.today().isoformat()},
        )

        current_price = _first_number(profile, quote, names=["price"])
        market_cap = _first_number(profile, quote, key_metrics, names=["marketCap", "mktCap"])
        dividend_yield = _first_number(
            profile,
            ratios,
            key_metrics,
            names=["dividendYield", "dividendYieldTTM", "dividendYielTTM"],
        )
        if dividend_yield is None:
            last_dividend = _first_number(profile, key_metrics, names=["lastDiv", "dividendPerShareTTM"])
            if last_dividend is not None and current_price and current_price > 0:
                dividend_yield = last_dividend / current_price

        price_to_book = _first_number(
            profile,
            ratios,
            key_metrics,
            names=["priceToBookRatio", "priceToBookRatioTTM", "pbRatio", "ptbRatio"],
        )
        multi_year_low = _historical_low(history)

        return FmpMarketSnapshot(
            symbol=symbol,
            market_cap=market_cap,
            dividend_yield=dividend_yield,
            price_to_book=price_to_book,
            current_price=current_price,
            multi_year_low=multi_year_low,
        )

    def _first_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        payload = self._json(endpoint, params)
        if isinstance(payload, list) and payload:
            return payload[0] if isinstance(payload[0], dict) else {}
        if isinstance(payload, dict):
            return payload
        return {}

    def _json(self, endpoint: str, params: dict[str, Any]) -> Any:
        query = urlencode({**params, "apikey": self.api_key})
        url = f"{FMP_BASE_URL}/{endpoint}?{query}"
        try:
            with urlopen(url, timeout=30) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise RuntimeError("FMP rejected the API key or plan access.") from exc
            if exc.code == 402:
                self.plan_limited_endpoints.add(endpoint)
                return []
            if exc.code == 404:
                return []
            raise
        if self.pause_seconds:
            time.sleep(self.pause_seconds)
        return payload


def apply_fmp_filters(results: list[Any], config: ScreenerConfig, client: FmpClient) -> None:
    for result in results:
        if not result.passed:
            continue
        plan_limited_before = set(client.plan_limited_endpoints)
        try:
            snapshot = client.market_snapshot(result.cik, result.tickers, config.near_low_years)
        except RuntimeError as exc:
            result.failed_filters.append("fmp_api_error")
            result.warnings.append(str(exc))
            result.passed = False
            continue
        plan_limited_now = client.plan_limited_endpoints - plan_limited_before
        for endpoint in sorted(plan_limited_now):
            result.warnings.append(f"fmp_plan_limited:{endpoint}")
        if snapshot is None:
            result.failed_filters.append("missing_fmp_market_data")
            result.passed = False
            continue
        _apply_snapshot(result, snapshot, config)


def _apply_snapshot(result: Any, snapshot: FmpMarketSnapshot, config: ScreenerConfig) -> None:
    result.metrics["fmp_symbol"] = snapshot.symbol
    result.metrics["market_cap"] = snapshot.market_cap
    result.metrics["dividend_yield"] = snapshot.dividend_yield
    result.metrics["price_to_book"] = snapshot.price_to_book
    result.metrics["current_price"] = snapshot.current_price
    result.metrics["multi_year_low"] = snapshot.multi_year_low
    result.metrics["low_multiple"] = snapshot.low_multiple

    if snapshot.market_cap is None:
        result.failed_filters.append("missing_market_cap")
    elif snapshot.market_cap >= config.market_cap_max:
        result.failed_filters.append("market_cap_too_high")

    if snapshot.dividend_yield is None:
        result.failed_filters.append("missing_dividend_yield")
    elif snapshot.dividend_yield < config.dividend_yield_min:
        result.failed_filters.append("low_dividend_yield")

    if snapshot.price_to_book is None:
        result.failed_filters.append("missing_price_to_book")
    elif snapshot.price_to_book >= config.price_to_book_max:
        result.failed_filters.append("price_to_book_too_high")

    if snapshot.low_multiple is None:
        result.failed_filters.append("missing_multi_year_low")
    elif snapshot.low_multiple > config.near_low_max_multiple:
        result.failed_filters.append("not_near_multi_year_low")

    result.passed = not result.failed_filters


def _first_symbol(tickers: str) -> str:
    for ticker in tickers.split(";"):
        clean = ticker.strip()
        if clean:
            return clean
    return ""


def _first_number(*payloads: dict[str, Any], names: list[str]) -> float | None:
    for payload in payloads:
        for name in names:
            value = payload.get(name)
            number = _to_float(value)
            if number is not None:
                return number
    return None


def _historical_low(payload: Any) -> float | None:
    rows = payload.get("historical", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return None
    lows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        low = _to_float(row.get("low") if "low" in row else row.get("close"))
        if low is not None:
            lows.append(low)
    return min(lows) if lows else None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _years_ago(years: int) -> str:
    return (date.today() - timedelta(days=365 * years)).isoformat()
