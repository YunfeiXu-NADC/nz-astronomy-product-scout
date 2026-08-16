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
- Guardrails: Trade Me evidence capture is user initiated and limited to the currently visible page; there is no unattended crawling, automatic pagination, or removed-listing-to-sale inference.

## API Surface

- `POST /products/import` imports product candidates plus supplier and shipping CSV text.
- `POST /products`, `GET /products`, `GET /products/{id}`, `PATCH /products/{id}` manage candidates.
- `GET /products/{id}/economics` returns landed cost, fees, margin, profit, break-even price, and pass/reject reasons.
- `GET /business/targets` returns the monthly profit goal, per-order economics gates, provisional inventory-risk cap, test window, and required order run rate.
- `POST /business/inventory-risk` checks planned SKU quantities and landed unit costs against the initial inventory-risk cap.
- `POST /keywords/refresh` accepts refreshed Keyword Planner metrics.
- `POST /imports/refresh` accepts Stats NZ metrics as JSON or CSV text.
- `GET /dashboard/trademe` returns source-linked Trade Me market snapshots and derived evidence metrics.
- `POST /dashboard/trademe/snapshots` records a dated, source-linked active-listing sample; `DELETE /dashboard/trademe/snapshots/{id}` removes an incorrect observation.
- `POST /batches/rank` reads local CSV paths, writes a ranked opportunity CSV, and can persist a local SQLite state file.
- `POST /sources/1688/discover` parses 1688 HTML or JSON payloads into reviewable product, supplier-offer, and keyword-seed records without importing them automatically.
- `GET /opportunities` returns ranked opportunities with score and confidence.
- `GET /opportunities/{id}` returns product, economics, and score detail.
- `nz-product-scout google-ads-smoke` calls the real Google Ads API Keyword Planner endpoint for a small connectivity check.
- `nz-product-scout market-scan` refreshes a market-level keyword taxonomy and writes both raw metrics and synonym-safe segment summaries.
- `nz-product-scout keywords-refresh` reads keyword seeds and writes Google Ads-backed keyword metrics CSV.
- `nz-product-scout discover-1688` converts 1688 search/listing HTML or JSON snapshots into pipeline-ready product, supplier-offer, and keyword-seed CSVs.
- `nz-product-scout capture-1688` opens a dedicated local browser profile for manual login/navigation, then captures the visible 1688 page into auditable evidence plus pipeline-ready CSVs.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn -e ".[dev]"
.venv\Scripts\python -m pytest
$env:PYTHONPATH="src"; .venv\Scripts\python -m uvicorn product_scout.api:create_app --factory --reload
```

The API will be available at `http://127.0.0.1:8000`.
The bilingual research workspace is served at the same URL. It provides market demand, Trade Me market validation, conclusions, opportunity filters, live Google Ads refresh, and inventory-risk controls without exposing API credentials to the browser.

Trade Me observations are stored locally in `.local/market-validation/trademe_snapshots.json`. The workspace validates sample counts, records the source URL and observation date, and reports supply, price, bid-activity, and evidence-completeness metrics. It does not automatically paginate or treat a removed listing as a sale.

For the fastest capture, use the Chrome extension in `tools/trademe-capture-extension/`. Opening the extension automatically analyses the current Trade Me search-results page. Review the NZD price chips, click any incorrect price to exclude it, and choose **Save to Product Scout**. Copying page text into **Paste & analyse** remains available as a fallback. Detailed seller and count fields remain available under **Advanced evidence**.

### Trade Me Chrome Capture

1. Open `chrome://extensions` and enable Developer mode.
2. Choose **Load unpacked** and select `tools/trademe-capture-extension/`.
3. Keep Product Scout running at `http://127.0.0.1:8000`.
4. Open a Trade Me search-results page and click the extension.
5. Review the automatically detected prices, then choose **Save to Product Scout**.

The extension reads the current rendered page only after you click it. It sends aggregate evidence to the local API, does not export cookies or credentials, and does not run automatic pagination or background collection.

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

## Test Google Ads API Connectivity

After `.env` contains the Google Ads developer token, OAuth client, refresh token, manager customer ID, and client customer ID, run:

```powershell
.venv\Scripts\python -m product_scout.cli google-ads-smoke `
  --keyword "telescope adapter" `
  --keyword "bahtinov mask"
```

The command uses `New Zealand`, `English`, and REST transport by default, then prints only keyword metric data. It does not create, edit, or manage Google Ads campaigns. Use `--transport grpc` only when the local network supports Google Ads gRPC reliably.

## Scan The NZ Astronomy Market

The Phase 0 market scan runs before 1688 sourcing. It groups related search terms into intent clusters and uses only the strongest keyword in each cluster when calculating a conservative segment demand index, so close synonyms are not added together.

```powershell
.venv\Scripts\python -m product_scout.cli market-scan `
  --seeds research\nz_astronomy_market_keywords.csv `
  --output research\nz_astronomy_market_metrics.csv `
  --summary research\nz_astronomy_market_summary.csv
```

The committed seed taxonomy is astronomy-specific. The mechanics are reusable, but V1 deliberately does not widen the product scope until the astronomy path has been validated.

## Refresh Real Keyword Metrics

Create or update `keyword_seeds.csv` with one keyword seed per product and cluster:

```csv
product_id,keyword,keyword_cluster
prod_1,m48 t2 adapter,m48_t2_adapter
prod_1,telescope t adapter,m48_t2_adapter
```

Then refresh Google Ads historical metrics into the standard keyword metrics CSV used by the ranking pipeline:

```powershell
.venv\Scripts\python -m product_scout.cli keywords-refresh `
  --products sample_data/products.csv `
  --keyword-seeds sample_data/keyword_seeds.csv `
  --output sample_data/keyword_metrics.csv
```

After that, rerun the normal rank command. The refresh command uses `New Zealand`, `English`, and REST transport by default.

## Discover 1688 Candidate Products

Use `discover-1688` when you do not already have product CSVs. It can read a saved 1688 HTML page, a JSON payload/export, or a direct URL. Direct URL fetching uses a normal HTTP request only; it does not bypass login, CAPTCHA, or anti-bot controls.

```powershell
.venv\Scripts\python -m product_scout.cli discover-1688 `
  --source-json sample_data/1688_discovery_sample.json `
  --output-products sample_data/products.csv `
  --output-suppliers sample_data/supplier_offers.csv `
  --output-keyword-seeds sample_data/keyword_seeds.csv
```

The discovery layer infers V1 target categories such as thread adapters, spacers, nosepiece adapters, camera adapters, brackets, Bahtinov masks, dust caps, and filter cases. Solar, laser, battery, and powered-electronics terms are preserved as risk flags so the existing risk engine can block them during scoring.

## Capture 1688 From A Logged-In Browser

Install the optional browser dependency from the Tsinghua mirror. The default command uses the locally installed Microsoft Edge, so it does not need to download a separate Chromium build.

```powershell
.venv\Scripts\python -m pip install `
  -i https://pypi.tuna.tsinghua.edu.cn/simple `
  --trusted-host pypi.tuna.tsinghua.edu.cn `
  -e ".[browser]"
```

Start a capture session:

```powershell
.venv\Scripts\python -m product_scout.cli capture-1688
```

A dedicated Edge window opens. Log in normally, complete any CAPTCHA yourself, and navigate to a 1688 search-results or product-detail page. Return to the terminal and press Enter. Each run writes a timestamped directory under `output/1688-captures/` containing `capture.json`, `source.png`, `products.csv`, `supplier_offers.csv`, and `keyword_seeds.csv`.

The browser profile is kept under `.local/1688-browser-profile/` so the login session can be reused. Both the profile and capture output are ignored by Git. Cookies, local storage, and credentials are not copied into `capture.json`. Raw page HTML is not saved unless `--save-html` is explicitly supplied.

This workflow does not automate login, solve CAPTCHAs, evade anti-bot controls, or call undocumented private endpoints. If Microsoft Edge is unavailable, install Playwright Chromium and run with `--browser-channel chromium`.

### Normal Chrome Fallback

If the isolated Playwright browser cannot complete the 1688/Taobao login flow, use the local extension in `tools/1688-capture-extension/` with the normal Chrome profile that can already log in:

1. Open `chrome://extensions` and enable Developer mode.
2. Choose **Load unpacked** and select `tools/1688-capture-extension/`.
3. Open a logged-in 1688 search-results or product-detail page.
4. Open the extension and choose **Capture current page**.

The extension downloads a normalized `1688-capture-*.json` file without cookies or credentials. Convert it through the existing discovery pipeline:

```powershell
.venv\Scripts\python -m product_scout.cli discover-1688 `
  --source-json "$env:USERPROFILE\Downloads\1688-capture-<timestamp>.json" `
  --output-products output\products.csv `
  --output-suppliers output\supplier_offers.csv `
  --output-keyword-seeds output\keyword_seeds.csv
```

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
GOOGLE_ADS_API_VERSION
```

## Data Notes

- `schema/postgresql.sql` contains the PostgreSQL schema for production persistence.
- `sample_data/` contains CSV shapes for discovered product candidates, supplier offers, shipping rates, keyword seeds, HS mapping, and Stats NZ import metrics.
- `product_scout.cli` runs the offline Sprint 1-3 pipeline without starting the API.
- Real Google Ads API credentials are intentionally not hardcoded; use local `.env` values or inject a client matching `KeywordPlannerClient` in `product_scout.google_ads`.
- `NZ_Astronomy_Product_Scout_Google_Ads_API_Design.rtf` is a short tool-design document for Google Ads API Basic Access review.

## Compliance Notes

- Unattended Trade Me crawling, automatic pagination, anti-bot bypass, and removed-listing-to-sale inference are intentionally out of scope.
- The optional Trade Me extension performs a user-initiated capture of the currently rendered search page and keeps the source URL and observation date for auditability.
- Prefer official Trade Me endpoints and first-party seller data whenever the required data is available through them.
- Supplier and logistics data should come from official APIs, authorized exports, or explicitly provided quote tables.
- Generated local state files such as SQLite databases and `.env` secrets are ignored by git.
