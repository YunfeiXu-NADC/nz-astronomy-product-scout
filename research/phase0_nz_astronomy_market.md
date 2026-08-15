# Phase 0: New Zealand Astronomy Market Attractiveness

Snapshot date: 2026-08-16

Market: New Zealand

Language: English

Decision scope: whether astronomy is worth further product discovery, not whether inventory should be purchased.

## Decision

**GO to Phase 1 opportunity-cluster discovery. Do not approve inventory yet.**

New Zealand has measurable upper-funnel demand for telescopes, astronomy, and stargazing. The current evidence does not support building a store around obscure telescope adapters alone. Functional accessories are a narrow, high-intent add-on market and should be attached to broader beginner astronomy, stargazing, astrophotography, education, or gift demand.

The recommended V1 position is:

> A content-led New Zealand astronomy store that solves beginner and compatibility problems, with low-risk accessories and small bundles as the first sourcing targets.

## Evidence Summary

The Google Ads scan used live Keyword Planner historical metrics for New Zealand and English. Closely related keywords were assigned to an `intent_cluster`; only the strongest keyword in each cluster contributes to the conservative demand index. The index is for relative comparison and must not be interpreted as unique users, orders, or addressable-market size.

| Segment | Conservative demand index | Intent clusters | Median cluster searches | Peak / average | Phase 0 status |
| --- | ---: | ---: | ---: | ---: | --- |
| Core astronomy market | 6,720 | 4 | 1,750 | 1.20 | GO |
| Astronomy gifts | 930 | 5 | 210 | 1.34 | WATCH |
| Matariki | 310 | 2 | 155 | 5.39 | HOLD |
| Education and STEM | 280 | 2 | 140 | 1.57 | WATCH |
| Functional accessories | 170 | 10 | 10 | 1.21 | WATCH / add-on |

Key live keyword observations:

| Keyword | Average monthly searches | Competition index | Interpretation |
| --- | ---: | ---: | --- |
| `telescope` | 2,900 | 100 | Large category demand, but highly competitive and operationally harder |
| `astronomy` | 1,900 | 1 | Strong information interest, weak direct purchase intent |
| `stargazing` | 1,600 | 13 | Strong content and audience-building opportunity |
| `telescopes nz` | 1,600 | 100 | Strong local commercial intent and strong competition |
| `astrophotography` | 320 | 11 | Specialist audience with potential for compatibility-led content |
| `star map` | 480 | 78 | Gift/decor demand larger than accessory demand, but less specialist |
| `star projector` | 210 | 100 | Larger product demand with intense generic competition |
| `solar system model` | 170 | 91 | Education opportunity with generic-market competition |
| `bahtinov mask` | 30 | 56 | Small but precise accessory intent |
| `telescope eyepiece` | 30 | 79 | Small commercial accessory cluster |
| `telescope camera adapter` | 10 | 98 | Exact intent, insufficient as a standalone acquisition engine |
| `matariki decorations` | 260 | 99 | High seasonality and cultural-governance requirements |

The source taxonomy is in `nz_astronomy_market_keywords.csv`; full API results are in `nz_astronomy_market_metrics.csv`; the synonym-safe roll-up is in `nz_astronomy_market_summary.csv`.

## Segment Conclusions

### 1. Core astronomy and stargazing: GO

The upper funnel is large enough to justify continuing. The opportunity is not automatically in importing complete telescopes: those products have high competition, greater dimensional weight, more quality risk, and more demanding after-sales support. Their demand can instead support content, compatibility guides, beginner kits, and accessory attachment.

### 2. Functional telescope accessories: WATCH / add-on

Accessory demand is fragmented. Most observed commercial terms are in the 10-30 monthly-search range. This is compatible with a narrow specialist catalog, but not with broad paid acquisition. Accessories should pass at least one of these tests:

- solve a documented compatibility problem;
- attach to a larger demand cluster such as beginner telescopes or astrophotography;
- form a bundle with a clear use case;
- have enough contribution profit to tolerate low order volume.

The existing 1688 adapter capture is therefore supply evidence for one cluster, not proof that adapters should define the store.

### 3. Astronomy gifts and education: WATCH

This area has more search demand than functional accessories, but it is less defensible and more crowded. It should be tested as a selective extension of the astronomy position, not allowed to turn the store into a generic novelty catalog.

### 4. Matariki: HOLD pending cultural review

The Google Ads history shows strong seasonality. Demand alone is not sufficient. Product concepts, naming, imagery, stories, and supplier artwork need cultural review and provenance checks. The official Matariki material describes values that should remain part of Matariki celebrations; that makes generic supplier artwork a material brand and cultural risk.

## External Evidence

- [Stats NZ imports and exports](https://www.stats.govt.nz/topics/imports-and-exports/) states that overseas merchandise trade provides monthly information about goods New Zealand imports and exports. It is the approved source for Phase 2 import validation.
- [New Zealand Customs Working Tariff Document](https://www.customs.govt.nz/business/tariffs/working-tariff-document/) is the reference for confirming the relevant tariff classification before HS-based import analysis.
- [Royal Astronomical Society of New Zealand](https://www.rasnz.org.nz/affiliated-societies) lists regional astronomical societies and describes its role in promoting astronomy. This supports the existence of an organised local enthusiast community, but does not quantify ecommerce demand.
- [Matariki official site](https://www.matariki.com/about) explains the principles and values associated with Matariki. It is a governance source, not a product-demand source.

## Phase 1 Entry Rules

A demand opportunity cluster can proceed to 1688 sourcing only when all applicable conditions are met:

1. **Primary cluster:** at least one commercial-intent keyword has 50 or more average monthly searches, or there is equivalent external evidence.
2. **Specialist add-on cluster:** at least one exact commercial keyword has 10 or more average monthly searches and the product attaches to a qualified primary cluster or bundle.
3. **Demand quality:** informational, commercial, compatibility, and seasonal intent are separated; close synonyms are not summed.
4. **Risk:** no safety-critical solar, laser, battery, or powered-electronics product enters V1.
5. **Economics:** estimated contribution margin is at least 30% and contribution profit is at least NZD 15 per order.
6. **Evidence confidence:** no product is marked `QUALIFIED` solely from Google Ads or solely from 1688 supply data.

## Next Research Work

1. Expand Google Ads from manually chosen keywords to Keyword Planner ideas for the four qualified themes: beginner astronomy, stargazing, astrophotography, and compatibility accessories.
2. Convert the resulting terms into demand opportunity clusters before searching 1688.
3. Complete manual New Zealand market snapshots for qualified clusters without automated Trade Me scraping.
4. Confirm tariff classifications and load Stats NZ import values for the most relevant product families.
5. Search 1688 only after a cluster passes the demand gate, then run logistics and unit-economics qualification.

## Known Limitations

- Google Ads search volume is rounded planning data, not sales data.
- The conservative demand index still compares search clusters; it is not a TAM estimate.
- Google Trends long-run normalized interest has not yet been persisted in the system.
- Exact Stats NZ product-family import values have not yet been loaded.
- Trade Me and local retailer price, assortment, review, and stock evidence remain manual gaps.
- Community presence does not establish purchase frequency or willingness to pay.
