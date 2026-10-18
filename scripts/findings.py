"""Headline numbers for the README, computed from the exported marts (the same files Power BI reads).

    python scripts/findings.py          (after `rx export`; writes reports/findings.json)

Costs are CMS "total drug cost": gross Part D spending at the pharmacy (ingredient cost, dispensing fee, sales
tax), before manufacturer rebates, which CMS does not publish per drug and prescriber.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "bi/exports"
OUT = ROOT / "reports/findings.json"


def mart(name: str) -> pd.DataFrame:
    return pd.read_parquet(EXPORTS / f"{name}.parquet")


def growth(new: float, old: float) -> float:
    return round(new / old - 1, 4)


def main() -> None:
    spend = mart("mart_drug_spend_trend")
    glp1 = mart("mart_glp1_growth")
    opp = mart("mart_generic_opportunity")
    dim = mart("dim_drug")
    years = sorted(int(y) for y in spend["data_year"].unique())
    first, last = years[0], years[-1]

    by_year = spend.groupby("data_year")[["drug_cost", "claims"]].sum()
    by_class_year = spend.groupby(["drug_class", "data_year"])[["drug_cost", "claims"]].sum()

    def cls(c: str, y: int, col: str) -> float:
        return float(by_class_year.loc[(c, y), col]) if (c, y) in by_class_year.index else 0.0

    total = {
        str(y): {
            "drug_cost": round(float(by_year.loc[y, "drug_cost"]), 2),
            "claims": int(by_year.loc[y, "claims"]),
            "cost_per_claim": round(float(by_year.loc[y, "drug_cost"] / by_year.loc[y, "claims"]), 2),
        }
        for y in years
    }
    glp1_year = glp1.groupby("data_year")[["claims", "drug_cost"]].sum()
    glp1_products = glp1[glp1["data_year"] == last].groupby("generic_name")["claims"].sum().sort_values(ascending=False)
    opioid = {
        str(y): {
            "opioid_analgesic_share_of_claims": round(
                cls("opioid_analgesic", y, "claims") / by_year.loc[y, "claims"], 4
            ),
            "oud_buprenorphine_claims_per_opioid_analgesic_claim": round(
                cls("opioid_use_disorder", y, "claims") / cls("opioid_analgesic", y, "claims"), 4
            ),
        }
        for y in years
    }
    opp_last = opp[opp["data_year"] == last]
    top_opp = opp_last.sort_values("savings_upper_bound", ascending=False).head(5)

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "bi/exports (marts from the 2022-2024 Florida Part D prescriber-drug files)",
        "note": "drug cost is gross Part D spending before manufacturer rebates",
        "florida_total": total,
        "drug_cost_growth": {
            f"{first}_to_{last}": growth(by_year.loc[last, "drug_cost"], by_year.loc[first, "drug_cost"])
        },
        "class_share_of_cost": {
            str(last): {
                c: round(cls(c, last, "drug_cost") / float(by_year.loc[last, "drug_cost"]), 4)
                for c in sorted(spend["drug_class"].unique())
            }
        },
        "glp1": {
            "claims": {str(y): int(glp1_year.loc[y, "claims"]) for y in years},
            "drug_cost": {str(y): round(float(glp1_year.loc[y, "drug_cost"]), 2) for y in years},
            "claims_growth": growth(glp1_year.loc[last, "claims"], glp1_year.loc[first, "claims"]),
            "cost_growth": growth(glp1_year.loc[last, "drug_cost"], glp1_year.loc[first, "drug_cost"]),
            f"top_products_{last}_by_claims": {k: int(v) for k, v in glp1_products.head(3).items()},
        },
        "opioids": opioid,
        "generic_opportunity": {
            f"upper_bound_{last}": round(float(opp_last["savings_upper_bound"].sum()), 2),
            f"top_{last}": [
                {
                    "generic_name": r.generic_name,
                    "drug_class": r.drug_class,
                    "brand_share_of_fills": round(float(r.brand_share_of_fills), 4),
                    "savings_upper_bound": round(float(r.savings_upper_bound), 2),
                }
                for r in top_opp.itertuples()
            ],
        },
        "products_per_class": {k: int(v) for k, v in dim["drug_class"].value_counts().sort_index().items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"florida_total": total, "glp1": report["glp1"]}, indent=1))


if __name__ == "__main__":
    main()
