"""Cut the CI sample from a full extract: real CMS records, small enough to commit.

    python scripts/make_fixtures.py ~/data/rx/raw tests/fixtures/pages

Keeps, for every data year:
- all rows of 25 Tampa prescribers (chosen by a hash of the NPI, so the choice is stable and not by volume), and
- one row per year of each product in dbt/tests/drug_class_edge_cases.sql, so the classification test has
  something to check in CI.
National spending: the "Overall" rows for the generic names in the sample, plus 20 manufacturer rows.
Prescriber names are dropped: nothing downstream uses them. Pages hold 250 rows, so loads read several files.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DROP = ("Prscrbr_Last_Org_Name", "Prscrbr_First_Name")
CITY, N_PRESCRIBERS, PAGE_ROWS = "Tampa", 25, 250


def pinned_products() -> set[tuple[str, str]]:
    path = ROOT / "dbt/tests/drug_class_edge_cases.sql"
    if not path.exists():
        return set()
    sql = path.read_text(encoding="utf-8")
    return {(b, g) for b, g, _ in re.findall(r"\('([^']+)', '([^']+)', '([^']+)'\)", sql)}


def records(year_dir: Path):
    for page in sorted(year_dir.glob("page-*.json")):
        yield from json.loads(page.read_text(encoding="utf-8"))


def key(npi: str) -> str:
    return hashlib.sha1(npi.encode()).hexdigest()  # noqa: S324 - a stable shuffle, not security


def write_pages(rows: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("page-*.json"):
        old.unlink()
    for i in range(0, len(rows), PAGE_ROWS):
        (out / f"page-{i // PAGE_ROWS:05d}.json").write_text(json.dumps(rows[i : i + PAGE_ROWS]), encoding="utf-8")


def main(raw: Path, out: Path) -> None:
    pinned = pinned_products()
    years = sorted(int(p.name) for p in (raw / "prescriber_drug").iterdir() if p.name.isdigit())
    tampa: dict[int, set[str]] = {y: set() for y in years}
    for y in years:
        tampa[y] = {r["Prscrbr_NPI"] for r in records(raw / "prescriber_drug" / str(y)) if r["Prscrbr_City"] == CITY}
    in_all_years = set.intersection(*tampa.values())
    chosen = set(sorted(in_all_years, key=key)[:N_PRESCRIBERS])

    generics: set[str] = set()
    for y in years:
        kept, seen = [], set()
        for r in records(raw / "prescriber_drug" / str(y)):
            product = (r["Brnd_Name"].strip().lower(), r["Gnrc_Name"].strip().lower())
            if r["Prscrbr_NPI"] in chosen:
                kept.append(r)
            elif product in pinned and product not in seen:
                seen.add(product)
                kept.append(r)
        for r in kept:
            for field in DROP:
                r.pop(field, None)
            generics.add(r["Gnrc_Name"].strip().lower())
        write_pages(kept, out / "prescriber_drug" / str(y))
        print(f"prescriber_drug {y}: {len(kept)} rows ({len(seen)} pinned products)")

    for spend_dir in sorted((raw / "spending_by_drug").iterdir()):
        rows = [r for r in records(spend_dir) if r["Gnrc_Name"].strip().lower() in generics]
        # The "Overall" rows are what the models use; a few manufacturer rows check that they are filtered out.
        kept = [r for r in rows if r["Mftr_Name"].strip() == "Overall"]
        kept += [r for r in rows if r["Mftr_Name"].strip() != "Overall"][:20]
        write_pages(kept, out / "spending_by_drug" / spend_dir.name)
        print(f"spending_by_drug {spend_dir.name}: {len(kept)} rows")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]).expanduser(), Path(sys.argv[2]))
