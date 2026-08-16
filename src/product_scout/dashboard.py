from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .market_scan import (
    export_market_metrics_csv,
    export_market_summary_csv,
    import_market_seeds_csv,
    run_market_scan,
    summarize_market_segments,
)
from .persistence import SQLiteRepositoryStore
from .repository import InMemoryRepository


SEGMENT_COPY = {
    "core_market": {
        "zh": "核心天文市场",
        "en": "Core astronomy market",
        "status": "GO",
    },
    "astronomy_gifts": {
        "zh": "天文礼品",
        "en": "Astronomy gifts",
        "status": "WATCH",
    },
    "matariki": {
        "zh": "Matariki",
        "en": "Matariki",
        "status": "HOLD",
    },
    "education_stem": {
        "zh": "教育与 STEM",
        "en": "Education and STEM",
        "status": "WATCH",
    },
    "functional_accessories": {
        "zh": "功能配件",
        "en": "Functional accessories",
        "status": "ADD-ON",
    },
}


REPORT_CONTENT = {
    "decision": {
        "zh": "进入需求机会簇发现阶段，但暂不批准采购库存。",
        "en": "Proceed to demand opportunity-cluster discovery, but do not approve inventory yet.",
    },
    "positioning": {
        "zh": "以数据研究和可验证的兼容性工具为基础，逐步建立产品知识；先测试容易理解、容易验货、低安全风险和低兼容性风险的天文周边。",
        "en": "Build product knowledge through evidence and verifiable compatibility tools, starting with astronomy products that are easy to understand, inspect, and support.",
    },
    "findings": [
        {
            "zh": "望远镜、天文学和观星存在明确的上层搜索需求，足以支持继续研究。",
            "en": "Telescope, astronomy, and stargazing searches provide enough upper-funnel demand to justify further research.",
        },
        {
            "zh": "多数功能配件关键词只有每月 10–30 次搜索，适合作为附加商品，而不是单独承担店铺获客。",
            "en": "Most functional-accessory terms receive only 10–30 monthly searches, making them add-ons rather than a standalone acquisition engine.",
        },
        {
            "zh": "每单贡献利润 NZ$20 意味着每月需要约 150 单；只卖低搜索量配件难以达到目标。",
            "en": "At NZ$20 contribution profit per order, roughly 150 monthly orders are required; low-volume accessories alone are unlikely to reach that run rate.",
        },
        {
            "zh": "当前 1688 转接环结果只能视为供应研究，兼容性和实物测试完成前不能直接采购。",
            "en": "The current 1688 adapter results are supply research only and are not purchase-ready without compatibility and sample verification.",
        },
    ],
    "next_steps": [
        {
            "zh": "建立望远镜系统地图、接口标准和用户问题库。",
            "en": "Build the telescope-system map, interface taxonomy, and user-problem library.",
        },
        {
            "zh": "扩展入门观星、天文摄影和兼容性配件的关键词机会簇。",
            "en": "Expand keyword opportunity clusters for beginner stargazing, astrophotography, and compatibility accessories.",
        },
        {
            "zh": "通过需求门槛后再找 1688 商品，并执行样品与库存风险检查。",
            "en": "Search 1688 only after the demand gate, followed by sample and inventory-risk checks.",
        },
    ],
}


class DashboardDataService:
    def __init__(self, data_root: str | Path, repository: InMemoryRepository) -> None:
        self.data_root = Path(data_root)
        self.repository = repository

    @property
    def market_seed_path(self) -> Path:
        return self.data_root / "research" / "nz_astronomy_market_keywords.csv"

    @property
    def market_metric_path(self) -> Path:
        return self.data_root / "research" / "nz_astronomy_market_metrics.csv"

    @property
    def market_summary_path(self) -> Path:
        return self.data_root / "research" / "nz_astronomy_market_summary.csv"

    def overview(self) -> dict[str, Any]:
        market = self.market()
        opportunities = self.opportunities()
        qualified = sum(item.get("status") == "QUALIFIED" for item in opportunities["items"])
        rejected = sum(item.get("status") == "REJECT" for item in opportunities["items"])
        return {
            "report": REPORT_CONTENT,
            "market": market,
            "opportunity_counts": {
                "total": len(opportunities["items"]),
                "qualified": qualified,
                "rejected": rejected,
            },
            "data_sources": {
                "market": str(self.market_metric_path),
                "opportunities": opportunities["source"],
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def market(self) -> dict[str, Any]:
        summaries = self._read_csv(self.market_summary_path)
        metrics = self._read_csv(self.market_metric_path)
        for summary in summaries:
            copy = SEGMENT_COPY.get(summary.get("segment", ""), {})
            summary["label_zh"] = copy.get("zh", summary.get("segment", ""))
            summary["label_en"] = copy.get("en", summary.get("segment", ""))
            summary["status"] = copy.get("status", "WATCH")
        return {
            "summaries": summaries,
            "metrics": metrics,
            "updated_at": self._modified_at(self.market_metric_path),
        }

    def opportunities(self) -> dict[str, Any]:
        if self.repository.score_snapshots:
            items = []
            for snapshot in self.repository.score_snapshots.values():
                row = snapshot.model_dump(mode="json")
                economics = self.repository.economics_by_product.get(snapshot.product_id)
                if economics:
                    row.update(
                        {
                            "contribution_profit_nzd": str(
                                economics.contribution_profit_nzd
                            ),
                            "contribution_margin": str(economics.contribution_margin),
                            "landed_cost_nzd": str(economics.landed_cost_nzd),
                        }
                    )
                items.append(row)
            items.sort(key=lambda item: float(item.get("prelaunch_score", 0)), reverse=True)
            return {"items": items, "source": "in_memory_repository"}

        source = self._latest_opportunity_csv()
        items = self._read_csv(source) if source else []
        if source:
            stores = sorted(
                [*source.parent.glob("*.sqlite"), *source.parent.glob("*.db")],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if stores:
                stored_repo = SQLiteRepositoryStore(stores[0]).load()
                for item in items:
                    economics = stored_repo.economics_by_product.get(
                        item.get("product_id", "")
                    )
                    if economics:
                        item.update(
                            {
                                "contribution_profit_nzd": str(
                                    economics.contribution_profit_nzd
                                ),
                                "contribution_margin": str(
                                    economics.contribution_margin
                                ),
                                "landed_cost_nzd": str(economics.landed_cost_nzd),
                            }
                        )
        return {
            "items": items,
            "source": str(source) if source else "none",
        }

    def refresh_market(self, client, *, location: str, language: str) -> dict[str, Any]:
        seeds = import_market_seeds_csv(
            self.market_seed_path.read_text(encoding="utf-8")
        )
        rows = run_market_scan(
            seeds,
            client,
            location=location,
            language=language,
        )
        summaries = summarize_market_segments(rows)
        export_market_metrics_csv(rows, self.market_metric_path)
        export_market_summary_csv(summaries, self.market_summary_path)
        return self.market()

    def _latest_opportunity_csv(self) -> Path | None:
        local_root = self.data_root / ".local" / "1688-import"
        candidates = list(local_root.glob("**/opportunities*.csv")) if local_root.exists() else []
        sample = self.data_root / "sample_data" / "opportunities.csv"
        if sample.exists():
            candidates.append(sample)
        return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None

    @staticmethod
    def _read_csv(path: Path | None) -> list[dict[str, str]]:
        if path is None or not path.exists():
            return []
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _modified_at(path: Path) -> str | None:
        if not path.exists():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
