from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .config import ScreenerConfig
from .sec_zip import normalize_cik


@dataclass(frozen=True)
class CompanySubmission:
    cik: str
    name: str
    sic: str
    tickers: str
    exchanges: str
    recent_filings: list[dict[str, str]]


def parse_submission(payload: dict[str, Any]) -> CompanySubmission:
    filings = payload.get("filings", {}).get("recent", {})
    recent_filings = _columnar_filings_to_rows(filings)
    return CompanySubmission(
        cik=normalize_cik(payload.get("cik") or payload.get("cik_str") or ""),
        name=str(payload.get("name") or ""),
        sic=str(payload.get("sic") or ""),
        tickers=";".join(_clean_text_list(payload.get("tickers"))),
        exchanges=";".join(_clean_text_list(payload.get("exchanges"))),
        recent_filings=recent_filings,
    )


def has_enough_filings(company: CompanySubmission, config: ScreenerConfig, today: date) -> tuple[bool, dict[str, int]]:
    min_year = today.year - config.recent_years
    annual_forms = set(config.annual_forms)
    quarterly_forms = set(config.quarterly_forms)
    years: set[int] = set()
    annual_count = 0
    quarterly_count = 0

    for filing in company.recent_filings:
        form = filing.get("form", "")
        filed = filing.get("filingDate", "")
        year = _safe_year(filing.get("reportDate") or filed)
        if year is None or year < min_year:
            continue
        if form in annual_forms:
            annual_count += 1
            years.add(year)
        elif form in quarterly_forms:
            quarterly_count += 1
            years.add(year)

    metrics = {
        "filing_years": len(years),
        "annual_reports": annual_count,
        "quarterly_reports": quarterly_count,
    }
    passed = (
        metrics["filing_years"] >= config.min_years_with_filings
        and annual_count >= config.min_annual_reports
        and quarterly_count >= config.min_quarterly_reports
    )
    return passed, metrics


def _columnar_filings_to_rows(filings: dict[str, list[Any]]) -> list[dict[str, str]]:
    if not filings:
        return []
    keys = list(filings.keys())
    row_count = max((len(value) for value in filings.values() if isinstance(value, list)), default=0)
    rows: list[dict[str, str]] = []
    for index in range(row_count):
        row = {}
        for key in keys:
            values = filings.get(key) or []
            row[key] = str(values[index]) if index < len(values) and values[index] is not None else ""
        rows.append(row)
    return rows


def _clean_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _safe_year(value: str) -> int | None:
    if len(value) < 4:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None
