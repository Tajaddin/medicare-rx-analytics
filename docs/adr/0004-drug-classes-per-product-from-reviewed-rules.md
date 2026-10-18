# 0004. Drug classes per product, from ordered rules reviewed against the data

Date: 2026-10-18. Status: accepted (bug #15).

## Context

The first version matched a class pattern against the generic name only. Listing every name each pattern
matched on the full 2022-2024 data showed real errors:

- `morphine` matched **apomorphine** (a Parkinson's drug), so it counted as an opioid.
- `naltrexone` matched **methylnaltrexone** (Relistor, for opioid-induced constipation) and
  **naltrexone/bupropion** (Contrave, for weight management), both counted as opioid-use-disorder treatment.
- `insulin` matched **syringes, pen needles and pump cartridges**.
- Codeine and hydrocodone **cough products** counted as analgesics.
- One generic name serves two uses: "Buprenorphine" is the Butrans pain patch and its generics (about $62 a
  unit nationally in 2024, four units a claim) and also Sublocade and Brixadi, monthly injections for OUD.

## Decision

- Classes are assigned per product (brand x generic name) by ordered rules in `seeds/drug_classes.csv`: generic
  and brand LIKE patterns, a priority, and a note giving the reason. The lowest priority wins; exceptions sit
  above the broad patterns.
- The opioid definitions follow CDC's opioid dispensing data: buprenorphine for pain (Belbuca, Butrans) counts
  as an analgesic, buprenorphine for OUD does not, cough and cold products are a separate class. Naltrexone is
  left out of OUD treatment because a prescription does not say whether it treats alcohol or opioid use.
- `tests/drug_class_edge_cases.sql` pins 23 reviewed products to their class; the CI sample carries a row of each
  one that appears in the Florida files (20 of the 23 in 2024; the rest exist only in the national file), so the
  test runs on every push.
- Marts that group by generic name include the class in their grain, so buprenorphine for pain and for OUD are
  never added together.

## Consequences

- A new product that only the broad pattern matches lands in the broad class until someone reviews it; the
  pinned test does not catch new names. Reviewing the per-class match list after each yearly load is in the
  runbook.
- A curated source (RxNorm/ATC through NLM's RxClass API) would scale better than patterns; it needs a mapping
  from CMS's abbreviated names ("Insulin Glargine,hum.Rec.Anlog") to RxNorm first.
