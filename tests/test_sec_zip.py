from __future__ import annotations

import json
from zipfile import ZipFile

from edgar_chip_screener.sec_zip import load_companyfacts_by_cik, normalize_cik


def test_normalize_cik_keeps_ten_digits() -> None:
    assert normalize_cik("2488") == "0000002488"
    assert normalize_cik("CIK0001045810") == "0001045810"


def test_load_companyfacts_by_cik_uses_direct_member_lookup(tmp_path, monkeypatch) -> None:
    zip_path = tmp_path / "companyfacts.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("CIK0000000001.json", json.dumps({"cik": 1}))
        archive.writestr("CIK0000000002.json", json.dumps({"cik": 2}))

    def fail_if_fallback_scans_zip(*args, **kwargs):
        raise AssertionError("companyfacts lookup should not scan the whole ZIP")

    monkeypatch.setattr("edgar_chip_screener.sec_zip.iter_json_zip", fail_if_fallback_scans_zip)
    loaded = load_companyfacts_by_cik(zip_path, {"1", "3"})

    assert loaded == {"0000000001": {"cik": 1}}
