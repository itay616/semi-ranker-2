from __future__ import annotations

import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEC_DOWNLOADS = {
    "submissions": (
        "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
        "submissions.zip",
    ),
    "companyfacts": (
        "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
        "companyfacts.zip",
    ),
}


def build_user_agent(contact_email: str, app_name: str = "semi-ranker-2") -> str:
    clean_email = contact_email.strip()
    if not clean_email or "@" not in clean_email:
        raise ValueError("SEC downloads require a real contact email for the User-Agent.")
    return f"{app_name}/0.1 contact={clean_email}"


def download_sec_bulk_files(
    output_dir: str | Path,
    contact_email: str,
    overwrite: bool = False,
    pause_seconds: float = 0.2,
) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    user_agent = build_user_agent(contact_email)
    downloaded: list[Path] = []

    for key, (url, filename) in SEC_DOWNLOADS.items():
        destination = output_path / filename
        if destination.exists() and not overwrite:
            print(f"Skipping existing {destination}")
            downloaded.append(destination)
            continue
        print(f"Downloading {key} to {destination}")
        _download_file(url, destination, user_agent)
        downloaded.append(destination)
        time.sleep(pause_seconds)
    return downloaded


def _download_file(url: str, destination: Path, user_agent: str) -> None:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "identity",
            "Host": "www.sec.gov",
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            with destination.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
    except HTTPError as exc:
        raise RuntimeError(
            f"SEC download failed with HTTP {exc.code}. "
            "Check that your contact email is valid and wait if SEC rate-limited your IP."
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"SEC download failed: {exc.reason}") from exc

