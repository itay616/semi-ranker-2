# EDGAR Chip Screener

A small Python project that screens chip and semiconductor-related SEC filers using only:

- SEC `submissions.zip`
- SEC `companyfacts.zip`

It applies these first-pass filters:

1. SIC belongs to semiconductor/chip-related industry
2. Has 5+ years of 10-Q/10-K or equivalent filings
3. Has usable XBRL company facts
4. CFO is positive over recent annual periods
5. FCF is positive over recent annual periods
6. CFO / Net Income is at least the configured threshold
7. Debt / Assets is at most 50%
8. Dividends are paid consistently, when dividend data is available
9. Acquisition spend is low relative to CFO or assets, when acquisition data is available

## Data

Download the two SEC bulk files with a declared SEC User-Agent:

```powershell
python -m edgar_chip_screener download `
  --contact-email you@example.com `
  --output-dir data/raw
```

This fetches:

- `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`
- `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip`

Put them anywhere locally, for example:

```text
data/raw/submissions.zip
data/raw/companyfacts.zip
```

The SEC expects automated requests to identify the tool and contact email. Do not use a fake email.

## Run

For a quick first test, run only a few semiconductor-related candidates:

```powershell
python -m edgar_chip_screener screen `
  --submissions data/raw/submissions.zip `
  --companyfacts data/raw/companyfacts.zip `
  --output outputs/chip_screen_sample.csv `
  --limit 10
```

To test one known CIK:

```powershell
python -m edgar_chip_screener screen `
  --submissions data/raw/submissions.zip `
  --companyfacts data/raw/companyfacts.zip `
  --output outputs/single_company.csv `
  --only-cik 0000320193
```

Useful chip-company test CIKs:

- AMD: `0000002488`
- Intel: `0000050863`
- Nvidia: `0001045810`

Run the full screen:

```powershell
python -m edgar_chip_screener screen `
  --submissions data/raw/submissions.zip `
  --companyfacts data/raw/companyfacts.zip `
  --output outputs/chip_screen.csv
```

Optional config override:

```powershell
python -m edgar_chip_screener screen `
  --submissions data/raw/submissions.zip `
  --companyfacts data/raw/companyfacts.zip `
  --config config/default.json `
  --output outputs/chip_screen.csv
```

## Output

The CSV includes one row per chip-related filer found in `submissions.zip`, with:

- company metadata
- whether the company passed
- failed filters
- warnings where SEC data is unavailable
- CFO, FCF, CFO/net income, debt/assets, dividends, and acquisition metrics

## Notes

This is a first-pass SEC-only screener. It intentionally does not check market cap, dividend yield, price/book, credit rating, or historical price lows because those require market or ratings data outside the two SEC ZIPs.
