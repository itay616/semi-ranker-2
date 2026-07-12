from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .config import ScreenerConfig
from .facts import Fact, iter_company_facts, latest_annual_by_year, latest_instant_fact
from .sec_zip import iter_json_zip, load_companyfacts_by_cik, load_submissions_by_cik, normalize_cik
from .submissions import CompanySubmission, has_enough_filings, parse_submission


@dataclass
class ScreenResult:
    cik: str
    name: str
    sic: str
    tickers: str
    exchanges: str
    passed: bool
    failed_filters: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed_filters": "; ".join(self.failed_filters),
            "warnings": "; ".join(self.warnings),
            "cik": self.cik,
            "name": self.name,
            "sic": self.sic,
            "tickers": self.tickers,
            "exchanges": self.exchanges,
            **self.metrics,
        }


def run_screen(
    submissions_zip: str | Path,
    companyfacts_zip: str | Path,
    config: ScreenerConfig,
    output_csv: str | Path,
    today: date | None = None,
    limit: int | None = None,
    only_ciks: list[str] | None = None,
) -> list[ScreenResult]:
    today = today or date.today()
    candidates = _load_submission_candidates(submissions_zip, config, limit, only_ciks)
    print(f"Found {len(candidates)} submission candidates. Loading matching company facts...")
    companyfacts = load_companyfacts_by_cik(companyfacts_zip, {company.cik for company in candidates})
    print(f"Loaded company facts for {len(companyfacts)} candidates. Running filters...")
    results = [
        _screen_company(company, companyfacts.get(company.cik), config, today)
        for company in candidates
    ]
    _write_results(output_csv, results)
    return results


def _load_submission_candidates(
    submissions_zip: str | Path,
    config: ScreenerConfig,
    limit: int | None = None,
    only_ciks: list[str] | None = None,
) -> list[CompanySubmission]:
    candidates: list[CompanySubmission] = []
    sic_codes = set(config.sic_codes)
    wanted_ciks = {normalize_cik(cik) for cik in only_ciks or []}
    if wanted_ciks:
        for payload in load_submissions_by_cik(submissions_zip, wanted_ciks).values():
            candidates.append(parse_submission(payload))
            if limit and len(candidates) >= limit:
                break
        return candidates

    for _, payload in iter_json_zip(submissions_zip):
        company = parse_submission(payload)
        if company.sic not in sic_codes:
            continue
        candidates.append(company)
        if limit and len(candidates) >= limit:
            break
    return candidates


def _screen_company(
    company: CompanySubmission,
    companyfacts: dict | None,
    config: ScreenerConfig,
    today: date,
) -> ScreenResult:
    result = ScreenResult(
        cik=company.cik,
        name=company.name,
        sic=company.sic,
        tickers=company.tickers,
        exchanges=company.exchanges,
        passed=True,
    )
    enough_filings, filing_metrics = has_enough_filings(company, config, today)
    result.metrics.update(filing_metrics)
    if not enough_filings:
        result.failed_filters.append("not_enough_filings")

    if not companyfacts:
        result.failed_filters.append("no_companyfacts")
        result.passed = False
        return result

    aliases = config.tag_aliases
    all_tags = sorted({tag for values in aliases.values() for tag in values})
    facts = list(iter_company_facts(companyfacts, all_tags))
    if not facts:
        result.failed_filters.append("no_usable_xbrl_facts")
        result.passed = False
        return result

    years = list(range(today.year - config.recent_years, today.year + 1))
    annual_forms = set(config.annual_forms)
    all_forms = set(config.annual_forms) | set(config.quarterly_forms)

    cfo = latest_annual_by_year(facts, aliases["cfo"], annual_forms, years)
    capex = latest_annual_by_year(facts, aliases["capex"], annual_forms, years, use_abs=True)
    net_income = latest_annual_by_year(facts, aliases["net_income"], annual_forms, years)
    dividends = latest_annual_by_year(facts, aliases["dividends"], annual_forms, years, use_abs=True)
    acquisitions = latest_annual_by_year(facts, aliases["acquisitions"], annual_forms, years, use_abs=True)
    assets_latest = latest_instant_fact(facts, aliases["assets"], all_forms, use_abs=True)
    debt_latest = _sum_latest_debt_facts(facts, aliases["debt"], all_forms)

    _apply_cfo_filter(result, cfo, config)
    _apply_fcf_filter(result, cfo, capex, config)
    _apply_cfo_net_income_filter(result, cfo, net_income, config)
    _apply_debt_assets_filter(result, debt_latest, assets_latest, config)
    _apply_dividend_filter(result, dividends, config)
    _apply_acquisition_filter(result, acquisitions, cfo, assets_latest, config)

    result.passed = not result.failed_filters
    return result


def _apply_cfo_filter(result: ScreenResult, cfo: dict[int, Fact], config: ScreenerConfig) -> None:
    recent = _last_n_year_values(cfo, config.recent_years)
    result.metrics["cfo_years_available"] = len(recent)
    result.metrics["cfo_positive_years"] = sum(1 for value in recent.values() if value > 0)
    result.metrics["latest_cfo"] = _latest_value(cfo)
    if len(recent) < config.recent_years:
        result.failed_filters.append("missing_cfo_history")
    elif any(value <= 0 for value in recent.values()):
        result.failed_filters.append("non_positive_cfo")


def _apply_fcf_filter(
    result: ScreenResult,
    cfo: dict[int, Fact],
    capex: dict[int, Fact],
    config: ScreenerConfig,
) -> None:
    fcfs = {}
    for year, cfo_fact in cfo.items():
        capex_fact = capex.get(year)
        if capex_fact:
            fcfs[year] = cfo_fact.value - capex_fact.value
    recent = _last_n_plain_values(fcfs, config.recent_years)
    result.metrics["fcf_years_available"] = len(recent)
    result.metrics["fcf_positive_years"] = sum(1 for value in recent.values() if value > 0)
    result.metrics["latest_fcf"] = _latest_plain_value(fcfs)
    if len(recent) < config.recent_years:
        result.failed_filters.append("missing_fcf_history")
    elif any(value <= 0 for value in recent.values()):
        result.failed_filters.append("non_positive_fcf")


def _apply_cfo_net_income_filter(
    result: ScreenResult,
    cfo: dict[int, Fact],
    net_income: dict[int, Fact],
    config: ScreenerConfig,
) -> None:
    ratios = {}
    for year, cfo_fact in cfo.items():
        ni_fact = net_income.get(year)
        if ni_fact and ni_fact.value > 0:
            ratios[year] = cfo_fact.value / ni_fact.value
    recent = _last_n_plain_values(ratios, config.recent_years)
    result.metrics["cfo_net_income_years_available"] = len(recent)
    result.metrics["latest_cfo_net_income_ratio"] = _latest_plain_value(ratios)
    if len(recent) < config.recent_years:
        result.failed_filters.append("missing_cfo_net_income_history")
    elif any(value < config.cfo_to_net_income_min for value in recent.values()):
        result.failed_filters.append("low_cfo_to_net_income")


def _apply_debt_assets_filter(
    result: ScreenResult,
    debt: float | None,
    assets: Fact | None,
    config: ScreenerConfig,
) -> None:
    result.metrics["latest_debt"] = debt
    result.metrics["latest_assets"] = assets.value if assets else None
    if debt is None or assets is None or assets.value <= 0:
        result.failed_filters.append("missing_debt_assets")
        return
    ratio = debt / assets.value
    result.metrics["debt_assets_ratio"] = ratio
    if ratio > config.debt_to_assets_max:
        result.failed_filters.append("high_debt_to_assets")


def _apply_dividend_filter(
    result: ScreenResult,
    dividends: dict[int, Fact],
    config: ScreenerConfig,
) -> None:
    recent = _last_n_year_values(dividends, config.dividend_consistency_years)
    positive_years = sum(1 for value in recent.values() if value > 0)
    result.metrics["dividend_years_available"] = len(recent)
    result.metrics["dividend_positive_years"] = positive_years
    result.metrics["latest_dividends"] = _latest_value(dividends)
    if not dividends:
        message = "dividend_data_unavailable"
        if config.dividend_required:
            result.failed_filters.append(message)
        else:
            result.warnings.append(message)
        return
    if len(recent) < config.dividend_consistency_years or positive_years < config.dividend_consistency_years:
        result.failed_filters.append("inconsistent_dividends")


def _apply_acquisition_filter(
    result: ScreenResult,
    acquisitions: dict[int, Fact],
    cfo: dict[int, Fact],
    assets: Fact | None,
    config: ScreenerConfig,
) -> None:
    if not acquisitions:
        result.warnings.append("acquisition_data_unavailable")
        return
    latest_acq = _latest_value(acquisitions)
    latest_cfo = _latest_value(cfo)
    result.metrics["latest_acquisition_spend"] = latest_acq
    if latest_acq is None:
        result.warnings.append("acquisition_data_unavailable")
        return

    ratios = []
    if latest_cfo and latest_cfo > 0:
        ratio = latest_acq / latest_cfo
        result.metrics["acquisition_spend_cfo_ratio"] = ratio
        ratios.append(ratio <= config.acquisition_spend_to_cfo_max)
    if assets and assets.value > 0:
        ratio = latest_acq / assets.value
        result.metrics["acquisition_spend_assets_ratio"] = ratio
        ratios.append(ratio <= config.acquisition_spend_to_assets_max)
    if ratios and not any(ratios):
        result.failed_filters.append("high_acquisition_spend")


def _sum_latest_debt_facts(facts: list[Fact], debt_aliases: list[str], forms: set[str]) -> float | None:
    by_tag: dict[str, Fact] = {}
    for tag in debt_aliases:
        fact = latest_instant_fact(facts, [tag], forms, use_abs=True)
        if fact:
            by_tag[tag] = fact
    if not by_tag:
        return None
    return sum(fact.value for fact in by_tag.values())


def _last_n_year_values(facts_by_year: dict[int, Fact], n: int) -> dict[int, float]:
    years = sorted(facts_by_year)[-n:]
    return {year: facts_by_year[year].value for year in years}


def _last_n_plain_values(values_by_year: dict[int, float], n: int) -> dict[int, float]:
    years = sorted(values_by_year)[-n:]
    return {year: values_by_year[year] for year in years}


def _latest_value(facts_by_year: dict[int, Fact]) -> float | None:
    if not facts_by_year:
        return None
    return facts_by_year[max(facts_by_year)].value


def _latest_plain_value(values_by_year: dict[int, float]) -> float | None:
    if not values_by_year:
        return None
    return values_by_year[max(values_by_year)]


def _write_results(path: str | Path, results: list[ScreenResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [result.to_row() for result in results]
    metric_keys = sorted({key for row in rows for key in row if key not in _BASE_COLUMNS})
    fieldnames = [*_BASE_COLUMNS, *metric_keys]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


_BASE_COLUMNS = [
    "passed",
    "failed_filters",
    "warnings",
    "cik",
    "name",
    "sic",
    "tickers",
    "exchanges",
]
