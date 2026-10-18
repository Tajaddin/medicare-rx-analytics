# Data card

## Sources

| Dataset | Publisher | Years used | Rows loaded | Grain |
|---|---|---|---|---|
| [Medicare Part D Prescribers - by Provider and Drug](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug) | CMS | 2022, 2023, 2024 (Florida prescribers only) | 1,865,305 + 1,955,768 + 2,048,452 | prescriber (NPI) x brand name x generic name x year |
| [Medicare Part D Spending by Drug](https://data.cms.gov/summary-statistics-on-use-and-payments/medicare-medicaid-spending-by-drug/medicare-part-d-spending-by-drug) | CMS | 2020-2024 (one wide release) | 14,536 | brand x generic x manufacturer, national |

Row counts are the API's own counts, matched by the rows on disk (`reports/extract/manifest-*.json`) and by
the rows loaded (`reports/pipeline-run.json`). Extracted 2026-10-18 through the CMS data API; both datasets are
public use files published by a U.S. federal agency.

## What a row means

- **Prescriber x drug:** Part D prescription drug event records (100% of final-action PDE records) for one
  prescriber and one product in one year: claims, 30-day fills, days' supply, total drug cost, beneficiaries.
- **Total drug cost** is gross: what Medicare, the plan and the beneficiary paid at the pharmacy (ingredient
  cost, dispensing fee, sales tax). It does **not** reflect manufacturer rebates, which CMS may not disclose.
  Plan sponsors received $48.6 billion in Part D rebates in 2021 ([GAO-23-107056](https://www.gao.gov/products/gao-23-107056)),
  so net cost is materially lower, more so for branded drugs with large rebates.
- **Suppression:** CMS publishes a prescriber-drug row only with 11 or more claims, and blanks counts below 11
  (beneficiaries, the 65+ breakdown). Blanks stay NULL in every model; nothing is back-filled. Totals therefore
  undercount low-volume prescribing.

## Fields used and dropped

- Prescriber names are present in the source and dropped in staging; no model, export or report shows an
  individual. NPIs are public identifiers (NPPES) and are kept as the join key.
- No beneficiary-level data exists in either file.

## Known limits

- **Florida only, by the prescriber's practice state.** A Florida resident's prescription from an out-of-state
  prescriber is not here.
- **Part D only.** Drugs administered in a clinic and billed to Part B, and drugs paid in cash, are not in these
  files; injectable OUD treatment billed that way is missing from the OUD counts.
- **Brand vs generic** is inferred: CMS lists a generic product with its generic name as the brand name. An
  unbranded biologic (e.g. "Insulin Aspart") therefore counts as a generic.
- **Generic opportunity is an upper bound:** the generic name groups strengths and dosage forms (OxyContin's
  extended-release tablets share "Oxycodone Hcl" with immediate-release generics), and some brands have no
  interchangeable generic.
- **Drug classes** come from reviewed rules ([ADR 0004](adr/0004-drug-classes-per-product-from-reviewed-rules.md));
  "other" holds everything outside the nine tracked classes; it is not a clinical category.
- **The city** is the prescriber's practice city as reported to CMS; cities with fewer than 20 prescribers are
  left out of the opioid mart.

## Quality checks that run on every load

See [ARCHITECTURE.md](ARCHITECTURE.md#quality-gates): API-count match, load-count match, 37 dbt tests and the
extract read-back.
