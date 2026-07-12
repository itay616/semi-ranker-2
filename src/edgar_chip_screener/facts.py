from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Fact:
    tag: str
    unit: str
    value: float
    fiscal_year: int
    fiscal_period: str
    form: str
    filed: str
    accession_number: str
    start: str | None = None
    end: str | None = None


def iter_company_facts(companyfacts: dict[str, Any], tags: Iterable[str]) -> Iterable[Fact]:
    wanted = set(tags)
    facts_root = companyfacts.get("facts", {})
    for taxonomy in facts_root.values():
        for tag, tag_payload in taxonomy.items():
            if tag not in wanted:
                continue
            units = tag_payload.get("units", {})
            for unit, rows in units.items():
                for row in rows:
                    fact = _row_to_fact(tag, unit, row)
                    if fact:
                        yield fact


def latest_annual_by_year(
    facts: Iterable[Fact],
    aliases: list[str],
    annual_forms: set[str],
    years: list[int],
    use_abs: bool = False,
) -> dict[int, Fact]:
    result: dict[int, Fact] = {}
    priority = {tag: index for index, tag in enumerate(aliases)}
    for fact in facts:
        if fact.tag not in priority:
            continue
        if fact.fiscal_period != "FY" or fact.form not in annual_forms:
            continue
        if fact.fiscal_year not in years:
            continue
        value = abs(fact.value) if use_abs else fact.value
        candidate = Fact(**{**fact.__dict__, "value": value})
        current = result.get(fact.fiscal_year)
        if current is None or _is_better_fact(candidate, current, priority):
            result[fact.fiscal_year] = candidate
    return result


def latest_instant_fact(
    facts: Iterable[Fact],
    aliases: list[str],
    forms: set[str],
    use_abs: bool = False,
) -> Fact | None:
    priority = {tag: index for index, tag in enumerate(aliases)}
    best: Fact | None = None
    for fact in facts:
        if fact.tag not in priority or fact.form not in forms:
            continue
        value = abs(fact.value) if use_abs else fact.value
        candidate = Fact(**{**fact.__dict__, "value": value})
        if best is None or _is_better_fact(candidate, best, priority):
            best = candidate
    return best


def _row_to_fact(tag: str, unit: str, row: dict[str, Any]) -> Fact | None:
    try:
        value = float(row["val"])
        fiscal_year = int(row["fy"])
    except (KeyError, TypeError, ValueError):
        return None
    fiscal_period = str(row.get("fp") or "")
    form = str(row.get("form") or "")
    filed = str(row.get("filed") or "")
    accession_number = str(row.get("accn") or "")
    return Fact(
        tag=tag,
        unit=unit,
        value=value,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        form=form,
        filed=filed,
        accession_number=accession_number,
        start=row.get("start"),
        end=row.get("end"),
    )


def _is_better_fact(candidate: Fact, current: Fact, priority: dict[str, int]) -> bool:
    candidate_priority = priority.get(candidate.tag, 999)
    current_priority = priority.get(current.tag, 999)
    if candidate_priority != current_priority:
        return candidate_priority < current_priority
    return candidate.filed > current.filed

