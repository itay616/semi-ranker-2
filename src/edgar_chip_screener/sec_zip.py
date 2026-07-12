from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from zipfile import ZipFile


def iter_json_zip(path: str | Path) -> Iterable[tuple[str, dict]]:
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if not name.lower().endswith(".json"):
                continue
            with archive.open(name) as handle:
                yield name, json.load(handle)


def load_companyfacts_by_cik(path: str | Path, ciks: set[str]) -> dict[str, dict]:
    wanted = {normalize_cik(cik) for cik in ciks}
    loaded: dict[str, dict] = {}
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        for cik in wanted:
            member_name = f"CIK{cik}.json"
            if member_name not in names:
                continue
            with archive.open(member_name) as handle:
                loaded[cik] = json.load(handle)
    return loaded


def load_submissions_by_cik(path: str | Path, ciks: set[str]) -> dict[str, dict]:
    wanted = {normalize_cik(cik) for cik in ciks}
    loaded: dict[str, dict] = {}
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        for cik in wanted:
            member_name = f"CIK{cik}.json"
            if member_name not in names:
                continue
            with archive.open(member_name) as handle:
                loaded[cik] = json.load(handle)
    return loaded


def normalize_cik(value: str | int) -> str:
    digits = "".join(char for char in str(value) if char.isdigit())
    return digits.zfill(10)
