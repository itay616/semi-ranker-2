from __future__ import annotations

from datetime import date

from edgar_chip_screener.config import load_config
from edgar_chip_screener.download import build_user_agent
from edgar_chip_screener.screen import _load_submission_candidates, _screen_company
from edgar_chip_screener.submissions import CompanySubmission, parse_submission


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


def test_user_agent_requires_contact_email() -> None:
    assert build_user_agent("owner@example.com") == "semi-ranker-2/0.1 contact=owner@example.com"


def test_only_cik_skips_sic_filter(monkeypatch) -> None:
    config = load_config()
    payloads = {
        "0000000001": {"cik": 1, "name": "Apple", "sic": "3571", "filings": {"recent": {}}},
        "0000000002": {"cik": 2, "name": "Semi", "sic": "3674", "filings": {"recent": {}}},
    }
    monkeypatch.setattr(
        "edgar_chip_screener.screen.load_submissions_by_cik",
        lambda _, ciks: {cik: payloads[cik] for cik in ciks},
    )
    candidates = _load_submission_candidates("ignored.zip", config, only_ciks=["1"])
    assert [candidate.cik for candidate in candidates] == ["0000000001"]


def test_parse_submission_ignores_blank_tickers_and_exchanges() -> None:
    company = parse_submission(
        {
            "cik": 123,
            "name": "Messy Metadata Inc",
            "sic": "3674",
            "tickers": ["MMI", None, ""],
            "exchanges": ["Nasdaq", None, " "],
            "filings": {"recent": {}},
        }
    )
    assert company.tickers == "MMI"
    assert company.exchanges == "Nasdaq"


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
