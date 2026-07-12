from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any


REPO_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.json"


@dataclass(frozen=True)
class ScreenerConfig:
    sic_codes: list[str]
    recent_years: int = 5
    min_years_with_filings: int = 5
    min_annual_reports: int = 5
    min_quarterly_reports: int = 12
    annual_forms: list[str] = field(default_factory=list)
    quarterly_forms: list[str] = field(default_factory=list)
    cfo_to_net_income_min: float = 0.8
    debt_to_assets_max: float = 0.5
    dividend_required: bool = False
    dividend_consistency_years: int = 5
    acquisition_spend_to_cfo_max: float = 0.2
    acquisition_spend_to_assets_max: float = 0.05
    market_cap_max: float = 100_000_000_000
    dividend_yield_min: float = 0.02
    price_to_book_max: float = 1.0
    near_low_years: int = 5
    near_low_max_multiple: float = 1.15
    tag_aliases: dict[str, list[str]] = field(default_factory=dict)

    @property
    def filing_forms(self) -> set[str]:
        return set(self.annual_forms) | set(self.quarterly_forms)


def load_config(path: str | Path | None = None) -> ScreenerConfig:
    if path:
        with Path(path).open("r", encoding="utf-8") as handle:
            raw: dict[str, Any] = json.load(handle)
    elif REPO_DEFAULT_CONFIG_PATH.exists():
        with REPO_DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    else:
        raw = json.loads(files("edgar_chip_screener").joinpath("default_config.json").read_text())
    return ScreenerConfig(**raw)
