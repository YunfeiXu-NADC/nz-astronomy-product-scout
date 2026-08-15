from __future__ import annotations

from decimal import Decimal
import os
from pathlib import Path
import time
from typing import Protocol

from pydantic import BaseModel

from .models import KeywordMetric, ProductCandidate

_NZ_GEO_TARGET_CONSTANT = "geoTargetConstants/2554"
_ENGLISH_LANGUAGE_CONSTANT = "languageConstants/1000"


class GoogleKeywordPlanMetric(BaseModel):
    keyword: str
    monthly_searches: int
    monthly_history: list[int]
    competition_index: int | None = None
    bid_low: Decimal | None = None
    bid_high: Decimal | None = None


class GoogleAdsCredentialConfig(BaseModel):
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    customer_id: str
    login_customer_id: str | None = None
    geo_target: str = "New Zealand"
    language: str = "English"
    api_version: str = "v25"


class KeywordPlannerClient(Protocol):
    def historical_metrics(
        self,
        *,
        keywords: list[str],
        location: str,
        language: str,
    ) -> list[GoogleKeywordPlanMetric]:
        ...


class GoogleAdsKeywordRefreshService:
    """Refreshes Google Keyword Planner metrics with the V1 NZ/English scope."""

    def __init__(
        self,
        client: KeywordPlannerClient,
        *,
        location: str = "New Zealand",
        language: str = "English",
    ) -> None:
        self.client = client
        self.location = location
        self.language = language

    def refresh(
        self,
        products: list[ProductCandidate],
        keywords_by_product: dict[str, list[str]],
        cluster_by_keyword: dict[str, str],
    ) -> list[KeywordMetric]:
        metrics: list[KeywordMetric] = []
        products_by_id = {product.id: product for product in products}
        product_ids_by_keyword: dict[str, list[str]] = {}
        for product_id, keywords in keywords_by_product.items():
            if product_id not in products_by_id:
                continue
            clean_keywords = [_normalize_keyword(keyword) for keyword in keywords if keyword.strip()]
            for keyword in clean_keywords:
                owners = product_ids_by_keyword.setdefault(keyword, [])
                if product_id not in owners:
                    owners.append(product_id)

        if not product_ids_by_keyword:
            return []
        google_metrics = self.client.historical_metrics(
            keywords=list(product_ids_by_keyword),
            location=self.location,
            language=self.language,
        )
        for google_metric in google_metrics:
            normalized_keyword = _normalize_keyword(google_metric.keyword)
            for product_id in product_ids_by_keyword.get(normalized_keyword, []):
                metrics.append(
                    KeywordMetric(
                        product_id=product_id,
                        keyword=normalized_keyword,
                        keyword_cluster=cluster_by_keyword.get(
                            normalized_keyword,
                            normalized_keyword.replace(" ", "_"),
                        ),
                        monthly_searches=google_metric.monthly_searches,
                        monthly_history=google_metric.monthly_history,
                        competition_index=google_metric.competition_index,
                        bid_low=google_metric.bid_low,
                        bid_high=google_metric.bid_high,
                    )
                )
        return metrics


class GoogleAdsKeywordPlannerClient:
    """Google Ads API client for Keyword Planner historical metrics."""

    def __init__(self, config: GoogleAdsCredentialConfig) -> None:
        self.config = config
        try:
            from google.ads.googleads.client import GoogleAdsClient
        except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
            raise RuntimeError(
                "google-ads is not installed. Install project dependencies before using "
                "the real Google Ads client."
            ) from exc

        client_config: dict[str, str | bool] = {
            "developer_token": config.developer_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "refresh_token": config.refresh_token,
            "use_proto_plus": True,
        }
        if config.login_customer_id:
            client_config["login_customer_id"] = _normalize_customer_id(config.login_customer_id)
        self._client = GoogleAdsClient.load_from_dict(client_config)

    def historical_metrics(
        self,
        *,
        keywords: list[str],
        location: str,
        language: str,
    ) -> list[GoogleKeywordPlanMetric]:
        normalized_keywords = [_normalize_keyword(keyword) for keyword in keywords if keyword.strip()]
        if not normalized_keywords:
            return []

        request = self._client.get_type("GenerateKeywordHistoricalMetricsRequest")
        request.customer_id = _normalize_customer_id(self.config.customer_id)
        request.keywords.extend(normalized_keywords)
        request.language = _language_resource_name(language)
        request.geo_target_constants.append(_geo_target_resource_name(location))
        request.keyword_plan_network = self._client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

        service = self._client.get_service("KeywordPlanIdeaService")
        response = service.generate_keyword_historical_metrics(request=request)
        return [_metric_from_google_result(result) for result in response.results]


class GoogleAdsRestKeywordPlannerClient:
    """REST fallback client for networks where Google Ads gRPC is unreliable."""

    def __init__(
        self,
        config: GoogleAdsCredentialConfig,
        *,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        try:
            import requests
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:  # pragma: no cover - exercised only without dependencies
            raise RuntimeError(
                "google-auth and requests are required for the REST Google Ads client."
            ) from exc
        self._requests = requests
        self._request_factory = Request
        self._credentials_factory = Credentials

    def historical_metrics(
        self,
        *,
        keywords: list[str],
        location: str,
        language: str,
    ) -> list[GoogleKeywordPlanMetric]:
        normalized_keywords = [_normalize_keyword(keyword) for keyword in keywords if keyword.strip()]
        if not normalized_keywords:
            return []

        credentials = self._credentials_factory(
            token=None,
            refresh_token=self.config.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            scopes=["https://www.googleapis.com/auth/adwords"],
        )
        credentials.refresh(self._request_factory())

        customer_id = _normalize_customer_id(self.config.customer_id)
        url = (
            f"https://googleads.googleapis.com/{self.config.api_version}/"
            f"customers/{customer_id}:generateKeywordHistoricalMetrics"
        )
        headers = {
            "Authorization": f"Bearer {credentials.token}",
            "developer-token": self.config.developer_token,
            "Content-Type": "application/json",
        }
        if self.config.login_customer_id:
            headers["login-customer-id"] = _normalize_customer_id(self.config.login_customer_id)

        request_body = {
            "keywords": normalized_keywords,
            "language": _language_resource_name(language),
            "geoTargetConstants": [_geo_target_resource_name(location)],
            "keywordPlanNetwork": "GOOGLE_SEARCH",
        }
        response = None
        for attempt in range(self.max_retries):
            try:
                response = self._requests.post(
                    url,
                    headers=headers,
                    json=request_body,
                    timeout=self.timeout_seconds,
                )
            except self._requests.exceptions.RequestException as exc:
                if attempt + 1 >= self.max_retries:
                    raise RuntimeError(
                        f"Google Ads network request failed after {self.max_retries} attempts: {exc}"
                    ) from exc
                time.sleep(2**attempt)
                continue
            if response.ok or response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt + 1 < self.max_retries:
                time.sleep(2**attempt)
        assert response is not None
        if not response.ok:
            raise RuntimeError(_format_google_ads_rest_error(response))
        data = response.json()
        return [_metric_from_rest_result(result) for result in data.get("results", [])]


def load_google_ads_config(env_file: str | Path = ".env") -> GoogleAdsCredentialConfig:
    """Load Google Ads credentials from .env plus process environment variables."""

    values = _read_env_file(Path(env_file))
    values.update({key: value for key, value in os.environ.items() if key.startswith("GOOGLE_ADS_")})
    required = {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "developer_token",
        "GOOGLE_ADS_CLIENT_ID": "client_id",
        "GOOGLE_ADS_CLIENT_SECRET": "client_secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "refresh_token",
        "GOOGLE_ADS_CUSTOMER_ID": "customer_id",
    }
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise ValueError("Missing Google Ads environment values: " + ", ".join(missing))

    return GoogleAdsCredentialConfig(
        developer_token=values["GOOGLE_ADS_DEVELOPER_TOKEN"],
        client_id=values["GOOGLE_ADS_CLIENT_ID"],
        client_secret=values["GOOGLE_ADS_CLIENT_SECRET"],
        refresh_token=values["GOOGLE_ADS_REFRESH_TOKEN"],
        customer_id=_normalize_customer_id(values["GOOGLE_ADS_CUSTOMER_ID"]),
        login_customer_id=_normalize_optional_customer_id(values.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")),
        geo_target=values.get("GOOGLE_ADS_GEO_TARGET") or "New Zealand",
        language=values.get("GOOGLE_ADS_LANGUAGE") or "English",
        api_version=values.get("GOOGLE_ADS_API_VERSION") or "v25",
    )


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.lower().split())


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _normalize_customer_id(customer_id: str) -> str:
    return "".join(character for character in customer_id if character.isdigit())


def _normalize_optional_customer_id(customer_id: str | None) -> str | None:
    if not customer_id:
        return None
    normalized = _normalize_customer_id(customer_id)
    return normalized or None


def _geo_target_resource_name(location: str) -> str:
    clean_location = location.strip()
    if clean_location.startswith("geoTargetConstants/"):
        return clean_location
    if clean_location.isdigit():
        return f"geoTargetConstants/{clean_location}"
    if clean_location.lower() == "new zealand":
        return _NZ_GEO_TARGET_CONSTANT
    raise ValueError(
        "Unsupported Google Ads geo target. Use 'New Zealand' or a "
        "geoTargetConstants/{id} resource name."
    )


def _language_resource_name(language: str) -> str:
    clean_language = language.strip()
    if clean_language.startswith("languageConstants/"):
        return clean_language
    if clean_language.isdigit():
        return f"languageConstants/{clean_language}"
    if clean_language.lower() == "english":
        return _ENGLISH_LANGUAGE_CONSTANT
    raise ValueError(
        "Unsupported Google Ads language. Use 'English' or a "
        "languageConstants/{id} resource name."
    )


def _metric_from_google_result(result) -> GoogleKeywordPlanMetric:
    metrics = result.keyword_metrics
    monthly_volumes = sorted(
        metrics.monthly_search_volumes,
        key=lambda volume: (int(volume.year), _month_number(volume.month)),
    )
    return GoogleKeywordPlanMetric(
        keyword=_normalize_keyword(result.text),
        monthly_searches=int(metrics.avg_monthly_searches),
        monthly_history=[int(volume.monthly_searches) for volume in monthly_volumes],
        competition_index=_optional_int(metrics.competition_index),
        bid_low=_micros_to_decimal(metrics.low_top_of_page_bid_micros),
        bid_high=_micros_to_decimal(metrics.high_top_of_page_bid_micros),
    )


def _metric_from_rest_result(result: dict) -> GoogleKeywordPlanMetric:
    metrics = result.get("keywordMetrics", {})
    monthly_volumes = sorted(
        metrics.get("monthlySearchVolumes", []),
        key=lambda volume: (int(volume.get("year", 0)), _month_number(volume.get("month", 0))),
    )
    return GoogleKeywordPlanMetric(
        keyword=_normalize_keyword(str(result.get("text", ""))),
        monthly_searches=int(metrics.get("avgMonthlySearches") or 0),
        monthly_history=[
            int(volume.get("monthlySearches") or 0) for volume in monthly_volumes
        ],
        competition_index=_optional_int(metrics.get("competitionIndex") or 0),
        bid_low=_micros_to_decimal(metrics.get("lowTopOfPageBidMicros") or 0),
        bid_high=_micros_to_decimal(metrics.get("highTopOfPageBidMicros") or 0),
    )


def _format_google_ads_rest_error(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Google Ads REST request failed with HTTP {response.status_code}: {response.text}"
    error = payload.get("error", {})
    details = error.get("details", [])
    ads_errors: list[str] = []
    for detail in details:
        for item in detail.get("errors", []):
            error_code = item.get("errorCode", {})
            code_name = next(iter(error_code.values()), "UNKNOWN")
            message = item.get("message", "")
            ads_errors.append(f"{code_name}: {message}".strip())
    suffix = "; ".join(ads_errors) if ads_errors else error.get("message", "")
    return f"Google Ads REST request failed with HTTP {response.status_code}: {suffix}"


def _optional_int(value) -> int | None:
    integer = int(value)
    return integer if integer else None


def _micros_to_decimal(value) -> Decimal | None:
    integer = int(value)
    if not integer:
        return None
    return Decimal(integer) / Decimal("1000000")


def _month_number(month) -> int:
    month_name = str(getattr(month, "name", "") or month)
    lookup = {
        "JANUARY": 1,
        "FEBRUARY": 2,
        "MARCH": 3,
        "APRIL": 4,
        "MAY": 5,
        "JUNE": 6,
        "JULY": 7,
        "AUGUST": 8,
        "SEPTEMBER": 9,
        "OCTOBER": 10,
        "NOVEMBER": 11,
        "DECEMBER": 12,
    }
    if month_name in lookup:
        return lookup[month_name]
    return max(0, int(month) - 1)
