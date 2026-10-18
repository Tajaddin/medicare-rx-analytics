# bi/exports

Written by `rx export` (the last stage of `scripts/run_pipeline.sh`); everything here except this file is
git-ignored and rebuilt from the marts.

| File | Read by |
|---|---|
| `<mart>.parquet` | the Power BI project (`bi/powerbi`, parameter ExportsFolder) |
| `<mart>.csv` | anything else |
| `rx_marts.hyper` | Tableau: one table per mart in schema `Extract`, verified against the marts after writing |
| `manifest.json` | rows and numeric column sums per mart, the values the `.hyper` read-back is checked against |

Column meanings: [docs/DATA-DICTIONARY.md](../../docs/DATA-DICTIONARY.md).
