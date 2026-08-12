# NZ Astronomy Product Scout V1

Internal ecommerce product research tool for evaluating New Zealand astronomy accessory demand using keyword planning, import statistics, supplier cost, and logistics data.

The first use case is ranking low-risk astronomy and astrophotography accessories, such as adapters, spacers, brackets, caps, and passive accessory kits, before sourcing inventory or running small ecommerce experiments.

## Google Ads API Usage

This project uses Google Ads API `KeywordPlanIdeaService` for internal keyword research and demand analysis. It retrieves keyword historical metrics such as average monthly searches, monthly search trends, competition index, and bid range data for New Zealand English keywords.

The tool does **not** create, manage, or optimize Google Ads campaigns. It does **not** manage third-party Google Ads accounts, scrape Google Search results, expose Google Ads API data to external users, or resell Google Ads API data.

Google Ads API credentials are not stored in this repository. Use `.env.example` as a template for local environment variables.

## What Is Implemented

- Sprint 1: product candidate CRUD, 1688-style supplier CSV import, shipping-rate CSV import, China-to-NZ direct landed-cost economics.
- Sprint 2: Google Keyword Planner refresh boundary fixed to `New Zealand` + `English`, keyword cluster scoring, synonym-safe demand aggregation.
- Sprint 3: Stats NZ import-metric CSV import, HS mapping confidence workflow, import evidence scoring, pre-launch opportunity ranking.
- Guardrails: no Trade Me competitor scraping; Trade Me market data is represented only as a manual-snapshot schema placeholder.

## API Surface

- `POST /products/import` imports product candidates plus supplier and shipping CSV text.
- `POST /products`, `GET /products`, `GET /products/{id}`, `PATCH /products/{id}` manage candidates.
- `GET /products/{id}/economics` returns landed cost, fees, margin, profit, break-even price, and pass/reject reasons.
- `POST /keywords/refresh` accepts refreshed Keyword Planner metrics.
- `POST /imports/refresh` accepts Stats NZ metrics as JSON or CSV text.
- `POST /batches/rank` reads local CSV paths, writes a ranked opportunity CSV, and can persist a local SQLite state file.
- `GET /opportunities` returns ranked opportunities with score and confidence.
- `GET /opportunities/{id}` returns product, economics, and score detail.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -e ".[dev]"
.venv\Scripts\python -m pytest
$env:PYTHONPATH="src"; .venv\Scripts\python -m uvicorn product_scout.api:create_app --factory --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Run A CSV Ranking Batch

```powershell
.venv\Scripts\python -m product_scout.cli rank `
  --products sample_data/products.csv `
  --suppliers sample_data/supplier_offers.csv `
  --shipping sample_data/shipping_rates.csv `
  --imports sample_data/stats_nz_import_metrics.csv `
  --keywords sample_data/keyword_metrics.csv `
  --output sample_data/opportunities.csv `
  --store sample_data/repository_state.json
```

This produces a sorted opportunity CSV with rank, score components, confidence, status, and rejection reasons.
Use `--sqlite-store sample_data/repository_state.sqlite` for a local SQLite state file, or pass a `.db` / `.sqlite` path to `--store`.

## Configuration

Copy `.env.example` to `.env` and fill only the credentials you actually have. Do not commit `.env`.

The Google Ads API fields are reserved for the planned real `KeywordPlanIdeaService` client:

```text
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
GOOGLE_ADS_LOGIN_CUSTOMER_ID
```

## Data Notes

- `schema/postgresql.sql` contains the PostgreSQL schema for production persistence.
- `sample_data/` contains CSV shapes for supplier offers, shipping rates, HS mapping, and Stats NZ import metrics.
- `product_scout.cli` runs the offline Sprint 1-3 pipeline without starting the API.
- Real Google Ads API credentials are intentionally not hardcoded; inject a client matching `KeywordPlannerClient` in `product_scout.google_ads`.
- `NZ_Astronomy_Product_Scout_Google_Ads_API_Design.rtf` is a short tool-design document for Google Ads API Basic Access review.

## Compliance Notes

- Trade Me competitor scraping is intentionally out of scope.
- Trade Me usage should be limited to allowed category/fee endpoints and the seller's own listing, sold, and unsold data.
- Supplier and logistics data should come from official APIs, authorized exports, or explicitly provided quote tables.
- Generated local state files such as SQLite databases and `.env` secrets are ignored by git.
