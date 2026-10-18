"""Three small CSVs for the Tableau Public dashboard, derived from the mart exports (run `make pipeline` first).

Tableau Public's web editor reads CSV uploads, not the .hyper extract, so each chart gets one tidy file with
readable column names. Written to bi/tableau-public/.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "bi" / "exports"
OUT = ROOT / "bi" / "tableau-public"
YEAR = 2024


def main() -> None:
    OUT.mkdir(exist_ok=True)

    glp1 = pd.read_csv(EXPORTS / "mart_glp1_growth.csv")
    glp1 = glp1.groupby(["generic_name", "data_year"], as_index=False)["claims"].sum()
    glp1.columns = ["Drug", "Year", "Claims"]
    glp1["Claims"] = glp1["Claims"].round().astype(int)
    glp1.to_csv(OUT / "glp1_claims_by_year.csv", index=False)

    cities = pd.read_csv(EXPORTS / "mart_opioid_by_city.csv")
    cities = cities[cities["data_year"] == YEAR].nlargest(15, "all_claims")
    cities = cities[["city", "all_claims", "opioid_claims", "opioid_share_of_claims"]]
    cities.columns = ["City", "All claims", "Opioid claims", "Opioid share of claims"]
    cities.to_csv(OUT / f"opioid_share_largest_cities_{YEAR}.csv", index=False)

    drugs = pd.read_csv(EXPORTS / "mart_drug_spend_trend.csv")
    drugs = drugs[drugs["data_year"] == YEAR].nlargest(10, "drug_cost")
    drugs = drugs[["generic_name", "drug_class", "drug_cost", "claims"]]
    drugs.columns = ["Drug", "Drug class", "Drug cost (USD)", "Claims"]
    drugs.to_csv(OUT / f"top_drugs_by_cost_{YEAR}.csv", index=False)

    for f in sorted(OUT.glob("*.csv")):
        print(f.relative_to(ROOT), len(pd.read_csv(f)), "rows")


if __name__ == "__main__":
    main()
