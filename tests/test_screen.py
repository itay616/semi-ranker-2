from __future__ import annotations

from datetime import date

from edgar_chip_screener.config import load_config
from edgar_chip_screener.screen import _screen_company
from edgar_chip_screener.submissions import CompanySubmission


def test_company_passes_core_filters_with_clean_annual_history() -> None:
    config = load_config()
    company = CompanySubmission(
        cik="0000000001",
        name="Example Semi",
        sic="3674",
        tickers="EXSM",
        exchanges="NYSE",
        recent_filings=_filings(),
    )
    result = _screen_company(company, _companyfacts(), config, date(2026, 7, 12))
    assert result.passed
    assert result.failed_filters == []
    assert result.metrics["latest_fcf"] == 750.0
    assert result.metrics["debt_assets_ratio"] == 0.25


def test_company_fails_negative_fcf() -> None:
    config = load_config()
    companyfacts = _companyfacts(capex=1200.0)
    company = CompanySubmission(
        cik="0000000001",
        name="Example Semi",
        sic="3674",
        tickers="EXSM",
        exchanges="NYSE",
        recent_filings=_filings(),
    )
    result = _screen_company(company, companyfacts, config, date(2026, 7, 12))
    assert not result.passed
    assert "non_positive_fcf" in result.failed_filters


def _filings() -> list[dict[str, str]]:
    rows = []
    for year in range(2021, 2027):
        rows.append({"form": "10-K", "filingDate": f"{year}-02-20", "reportDate": f"{year - 1}-12-31"})
        for quarter in range(1, 4):
            rows.append({"form": "10-Q", "filingDate": f"{year}-0{quarter + 2}-10", "reportDate": f"{year}-0{quarter * 3}-30"})
    return rows


def _companyfacts(capex: float = 250.0) -> dict:
    return {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {"USD": [_duration_fact(year, 1000.0) for year in range(2021, 2027)]}
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {"USD": [_duration_fact(year, capex) for year in range(2021, 2027)]}
                },
                "NetIncomeLoss": {
                    "units": {"USD": [_duration_fact(year, 900.0) for year in range(2021, 2027)]}
                },
                "PaymentsOfDividendsCommonStock": {
                    "units": {"USD": [_duration_fact(year, 100.0) for year in range(2021, 2027)]}
                },
                "PaymentsToAcquireBusinessesNetOfCashAcquired": {
                    "units": {"USD": [_duration_fact(year, 50.0) for year in range(2021, 2027)]}
                },
                "Assets": {
                    "units": {"USD": [_instant_fact(2026, 4000.0)]}
                },
                "LongTermDebt": {
                    "units": {"USD": [_instant_fact(2026, 1000.0)]}
                },
            }
        },
    }


def _duration_fact(year: int, value: float) -> dict:
    return {
        "val": value,
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": f"{year + 1}-02-20",
        "accn": f"{year}-000001",
        "start": f"{year}-01-01",
        "end": f"{year}-12-31",
    }


def _instant_fact(year: int, value: float) -> dict:
    return {
        "val": value,
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": f"{year + 1}-02-20",
        "accn": f"{year}-000001",
        "end": f"{year}-12-31",
    }

