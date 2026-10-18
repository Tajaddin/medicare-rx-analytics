"""Write the Power BI project (PBIP: TMDL semantic model + PBIR report) over the marts in bi/exports.

    python scripts/make_powerbi.py      (after `rx export`: column types come from the Parquet schemas)

Open bi/powerbi/MedicareRx.pbip in Power BI Desktop, set the ExportsFolder parameter to the absolute path of
bi/exports (Transform data > Edit parameters) and refresh. Generated rather than hand-saved so the model always
matches the marts and every lineage tag is stable between runs.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "bi/exports"
OUT = ROOT / "bi/powerbi"
NAME = "MedicareRx"
NS = uuid.UUID("6f1b2a5e-2d1c-4a8e-9a57-3c0f6d2b9e41")
THEME = "Fluent2-CY26SU10"
SCHEMAS = "https://developer.microsoft.com/json-schemas/fabric"
# Power Query needs an absolute path; RX_PBI_EXPORTS_FOLDER sets the default the project is written with.
DEFAULT_FOLDER = os.environ.get("RX_PBI_EXPORTS_FOLDER", r"C:\medicare-rx-analytics\bi\exports")

MARTS = [
    "mart_drug_spend_trend",
    "mart_specialty_class_year",
    "mart_generic_opportunity",
    "mart_opioid_by_city",
    "mart_glp1_growth",
    "dim_drug",
]
DESCRIPTIONS = {
    "mart_drug_spend_trend": "Florida Part D spend per generic name, class and year, with the national cost per claim.",
    "mart_specialty_class_year": "Claims and cost by prescriber specialty and therapeutic class.",
    "mart_generic_opportunity": "Brand spend where the same generic name was also dispensed, with an upper-bound saving.",
    "mart_opioid_by_city": "Opioid and OUD-treatment prescribing by city (cities with 20+ prescribers).",
    "mart_glp1_growth": "GLP-1 receptor agonists by product, specialty and year.",
    "dim_drug": "Products seen in Florida with class and national 2024 unit prices.",
}
MONEY, COUNT, PCT, DEC = r"\$#,0", "#,0", "0.0%", "#,0.00"

# (table, name, DAX, format, folder)
MEASURES = [
    ("mart_drug_spend_trend", "Total drug cost", "SUM(mart_drug_spend_trend[drug_cost])", MONEY, "Spend"),
    ("mart_drug_spend_trend", "Total claims", "SUM(mart_drug_spend_trend[claims])", COUNT, "Spend"),
    ("mart_drug_spend_trend", "Cost per claim", "DIVIDE([Total drug cost], [Total claims])", r"\$#,0.00", "Spend"),
    # Latest year in the filter context against the year before it; over several years that is the newest pair,
    # never the multi-year total against one year.
    (
        "mart_drug_spend_trend",
        "Drug cost latest year",
        "VAR y = MAX('Year'[data_year]) RETURN CALCULATE([Total drug cost], 'Year'[data_year] = y)",
        MONEY,
        "Spend",
    ),
    (
        "mart_drug_spend_trend",
        "Drug cost previous year",
        "VAR y = MAX('Year'[data_year]) RETURN CALCULATE([Total drug cost], 'Year'[data_year] = y - 1)",
        MONEY,
        "Spend",
    ),
    (
        "mart_drug_spend_trend",
        "Drug cost growth",
        "VAR prev = [Drug cost previous year] "
        "RETURN IF(NOT ISBLANK(prev), DIVIDE([Drug cost latest year] - prev, prev))",
        PCT,
        "Spend",
    ),
    ("mart_glp1_growth", "GLP-1 claims", "SUM(mart_glp1_growth[claims])", COUNT, "GLP-1"),
    ("mart_glp1_growth", "GLP-1 cost", "SUM(mart_glp1_growth[drug_cost])", MONEY, "GLP-1"),
    ("mart_glp1_growth", "GLP-1 prescribers", "SUM(mart_glp1_growth[prescribers])", COUNT, "GLP-1"),
    (
        "mart_generic_opportunity",
        "Saving upper bound",
        "SUM(mart_generic_opportunity[savings_upper_bound])",
        MONEY,
        "Generics",
    ),
    (
        "mart_generic_opportunity",
        "Brand share of fills",
        "DIVIDE(SUM(mart_generic_opportunity[brand_fills]), "
        "SUM(mart_generic_opportunity[brand_fills]) + SUM(mart_generic_opportunity[generic_fills]))",
        PCT,
        "Generics",
    ),
    (
        "mart_opioid_by_city",
        "Opioid share of claims",
        "DIVIDE(SUM(mart_opioid_by_city[opioid_claims]), SUM(mart_opioid_by_city[all_claims]))",
        "0.00%",
        "Opioids",
    ),
    (
        "mart_opioid_by_city",
        "OUD treatment per opioid claim",
        "DIVIDE(SUM(mart_opioid_by_city[oud_treatment_claims]), SUM(mart_opioid_by_city[opioid_claims]))",
        "0.000",
        "Opioids",
    ),
]
YEAR_FACTS = [
    "mart_drug_spend_trend",
    "mart_specialty_class_year",
    "mart_generic_opportunity",
    "mart_opioid_by_city",
    "mart_glp1_growth",
]
CLASS_FACTS = ["mart_drug_spend_trend", "mart_specialty_class_year", "mart_generic_opportunity", "dim_drug"]


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "/".join(parts)))


def dax_type(t: pa.DataType) -> str:
    if pa.types.is_integer(t):
        return "int64"
    if pa.types.is_floating(t) or pa.types.is_decimal(t):
        return "double"
    if pa.types.is_boolean(t):
        return "boolean"
    return "string"


RATIO_HINTS = ("per_", "share", "growth", "rank", "avg_")


def is_ratio(name: str) -> bool:
    """Ratios, shares, ranks and averages must not be summed by a visual."""
    return any(k in name for k in RATIO_HINTS)


def column_format(name: str, dtype: str) -> str | None:
    if dtype not in ("int64", "double") or name == "data_year":
        return "0" if name == "data_year" else None
    if any(k in name for k in ("share", "growth")):
        return PCT
    if "cost" in name or "spend" in name or "savings" in name:
        return r"\$#,0.00" if "per_" in name else MONEY
    return COUNT if dtype == "int64" or "claims" in name or "fills" in name else DEC


def summarize(name: str, dtype: str) -> str:
    return "sum" if dtype in ("int64", "double") and name != "data_year" and not is_ratio(name) else "none"


def m_parquet(file: str, extra: str = "") -> list[str]:
    body = [
        "let",
        f'    Source = Parquet.Document(File.Contents(ExportsFolder & "\\{file}.parquet"))' + ("," if extra else ""),
    ]
    if extra:
        body.append(extra)
    body += ["in", "    " + ("Result" if extra else "Source")]
    return body


def table_tmdl(name: str, schema: pa.Schema) -> str:
    lines = [f"/// {DESCRIPTIONS[name]}", f"table {name}", f"\tlineageTag: {tag(name)}", ""]
    for table, mname, dax, fmt, folder in MEASURES:
        if table != name:
            continue
        lines += [
            f"\tmeasure '{mname}' = {dax}",
            f"\t\tformatString: {fmt}",
            f"\t\tdisplayFolder: {folder}",
            f"\t\tlineageTag: {tag(name, 'measure', mname)}",
            "",
        ]
    for field in schema:
        dtype = dax_type(field.type)
        hidden = (field.name == "data_year" and name in YEAR_FACTS) or (
            field.name == "drug_class" and name in CLASS_FACTS
        )
        lines += [f"\tcolumn {field.name}", f"\t\tdataType: {dtype}"]
        fmt = column_format(field.name, dtype)
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        if hidden:
            lines.append("\t\tisHidden")
        lines += [
            f"\t\tlineageTag: {tag(name, field.name)}",
            f"\t\tsummarizeBy: {summarize(field.name, dtype)}",
            f"\t\tsourceColumn: {field.name}",
            "",
        ]
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource ="]
    lines += ["\t\t\t\t" + s for s in m_parquet(name)]
    return "\n".join(lines) + "\n"


def dimension_tmdl(name: str, column: str, dtype: str, source: str, description: str) -> str:
    extra = f'    Result = Table.Sort(Table.Distinct(Table.SelectColumns(Source, {{"{column}"}})), {{"{column}"}})'
    lines = [
        f"/// {description}",
        f"table {name}",
        f"\tlineageTag: {tag(name)}",
        "",
        f"\tcolumn {column}",
        f"\t\tdataType: {dtype}",
        *(["\t\tformatString: 0"] if dtype == "int64" else []),
        f"\t\tlineageTag: {tag(name, column)}",
        "\t\tsummarizeBy: none",
        f"\t\tsourceColumn: {column}",
        "",
        f"\tpartition {name} = m",
        "\t\tmode: import",
        "\t\tsource =",
        *["\t\t\t\t" + s for s in m_parquet(source, extra)],
    ]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj: object) -> None:
    write(path, json.dumps(obj, indent=2) + "\n")


def semantic_model(schemas: dict[str, pa.Schema]) -> None:
    sm = OUT / f"{NAME}.SemanticModel"
    write_json(
        sm / "definition.pbism",
        {
            "$schema": f"{SCHEMAS}/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {},
        },
    )
    d = sm / "definition"
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    tables = ["Year", "DrugClass", *MARTS]
    model = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tdiscourageImplicitMeasures",
        "\tsourceQueryCulture: en-US",
        "",
    ]
    model += [f"ref table {t}" for t in tables]
    model += ["", "ref expression ExportsFolder"]
    write(d / "model.tmdl", "\n".join(model) + "\n")
    write(
        d / "expressions.tmdl",
        "/// Absolute path of the bi/exports folder written by `rx export`.\n"
        f'expression ExportsFolder = "{DEFAULT_FOLDER}" meta [IsParameterQuery=true, Type="Text", '
        "IsParameterQueryRequired=true]\n"
        f"\tlineageTag: {tag('ExportsFolder')}\n\n\tannotation PBI_ResultType = Text\n",
    )
    for name in MARTS:
        write(d / "tables" / f"{name}.tmdl", table_tmdl(name, schemas[name]))
    write(
        d / "tables" / "Year.tmdl",
        dimension_tmdl("Year", "data_year", "int64", "mart_drug_spend_trend", "Data years in the marts."),
    )
    write(
        d / "tables" / "DrugClass.tmdl",
        dimension_tmdl("DrugClass", "drug_class", "string", "dim_drug", "Therapeutic classes from the reviewed rules."),
    )
    rels = []
    for fact in YEAR_FACTS:
        rels += [
            f"relationship {tag('rel', fact, 'Year')}",
            f"\tfromColumn: {fact}.data_year",
            "\ttoColumn: Year.data_year",
            "",
        ]
    for fact in CLASS_FACTS:
        rels += [
            f"relationship {tag('rel', fact, 'DrugClass')}",
            f"\tfromColumn: {fact}.drug_class",
            "\ttoColumn: DrugClass.drug_class",
            "",
        ]
    write(d / "relationships.tmdl", "\n".join(rels))


def col(entity: str, prop: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def measure(entity: str, prop: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def projection(field: dict) -> dict:
    kind = "Column" if "Column" in field else "Measure"
    entity = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    return {"field": field, "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def visual(
    name: str,
    vtype: str,
    pos: tuple[int, int, int, int],
    roles: dict[str, list[dict]],
    title: str,
    *,
    sort: tuple[dict, str] | None = None,
) -> dict:
    x, y, w, h = pos
    query: dict = {
        "queryState": {role: {"projections": [projection(f) for f in fields]} for role, fields in roles.items()}
    }
    if sort:
        query["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
    return {
        "$schema": f"{SCHEMAS}/item/report/definition/visualContainer/2.4.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": 0, "width": w, "height": h, "tabOrder": 0},
        "visual": {
            "visualType": vtype,
            "query": query,
            "visualContainerObjects": {
                "title": [
                    {"properties": {"text": {"expr": {"Literal": {"Value": json.dumps(title).replace('"', "'")}}}}}
                ]
            },
            "drillFilterOtherVisuals": True,
        },
    }


SPEND, GLP1, OPP, OPIOID = (
    "mart_drug_spend_trend",
    "mart_glp1_growth",
    "mart_generic_opportunity",
    "mart_opioid_by_city",
)
PAGES = {
    "spend": (
        "Spend",
        [
            visual(
                "costCard",
                "card",
                (20, 20, 300, 150),
                {"Values": [measure(SPEND, "Total drug cost")]},
                "Drug cost, years selected",
            ),
            visual(
                "claimsCard",
                "card",
                (340, 20, 300, 150),
                {"Values": [measure(SPEND, "Total claims")]},
                "Claims, years selected",
            ),
            visual(
                "perClaimCard",
                "card",
                (660, 20, 300, 150),
                {"Values": [measure(SPEND, "Cost per claim")]},
                "Cost per claim",
            ),
            visual(
                "growthCard",
                "card",
                (980, 20, 280, 150),
                {"Values": [measure(SPEND, "Drug cost growth")]},
                "Latest year vs the one before",
            ),
            visual(
                "costByYear",
                "clusteredColumnChart",
                (20, 190, 600, 510),
                {"Category": [col("Year", "data_year")], "Y": [measure(SPEND, "Total drug cost")]},
                "Drug cost by year",
            ),
            visual(
                "costByClass",
                "clusteredBarChart",
                (640, 190, 620, 510),
                {"Category": [col("DrugClass", "drug_class")], "Y": [measure(SPEND, "Total drug cost")]},
                "Drug cost by therapeutic class",
                sort=(measure(SPEND, "Total drug cost"), "Descending"),
            ),
        ],
    ),
    "glp1": (
        "GLP-1 and opioids",
        [
            visual(
                "glp1Trend",
                "lineChart",
                (20, 20, 620, 400),
                {
                    "Category": [col("Year", "data_year")],
                    "Y": [measure(GLP1, "GLP-1 claims")],
                    "Series": [col(GLP1, "generic_name")],
                },
                "GLP-1 claims by product",
            ),
            visual(
                "glp1Cost",
                "clusteredColumnChart",
                (660, 20, 600, 400),
                {"Category": [col("Year", "data_year")], "Y": [measure(GLP1, "GLP-1 cost")]},
                "GLP-1 drug cost",
            ),
            visual(
                "opioidCities",
                "tableEx",
                (20, 440, 900, 260),
                {
                    "Values": [
                        col(OPIOID, "city"),
                        measure(OPIOID, "Opioid share of claims"),
                        measure(OPIOID, "OUD treatment per opioid claim"),
                    ]
                },
                "Opioid share of claims by city",
                sort=(measure(OPIOID, "Opioid share of claims"), "Descending"),
            ),
            visual(
                "oudCard",
                "card",
                (940, 440, 320, 260),
                {"Values": [measure(OPIOID, "OUD treatment per opioid claim")]},
                "OUD treatment claims per opioid claim",
            ),
        ],
    ),
    "generics": (
        "Generic opportunity",
        [
            visual(
                "savingCard",
                "card",
                (20, 20, 400, 150),
                {"Values": [measure(OPP, "Saving upper bound")]},
                "Brand spend above generic cost (upper bound)",
            ),
            visual(
                "brandShareCard",
                "card",
                (440, 20, 400, 150),
                {"Values": [measure(OPP, "Brand share of fills")]},
                "Brand share of fills",
            ),
            visual(
                "savingTable",
                "tableEx",
                (20, 190, 1240, 510),
                {
                    "Values": [
                        col(OPP, "generic_name"),
                        col("DrugClass", "drug_class"),
                        measure(OPP, "Brand share of fills"),
                        measure(OPP, "Saving upper bound"),
                    ]
                },
                "Largest brand-over-generic spend",
                sort=(measure(OPP, "Saving upper bound"), "Descending"),
            ),
        ],
    ),
}


def report() -> None:
    rp = OUT / f"{NAME}.Report"
    write_json(
        rp / "definition.pbir",
        {
            "$schema": f"{SCHEMAS}/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
        },
    )
    d = rp / "definition"
    write_json(
        d / "version.json",
        {"$schema": f"{SCHEMAS}/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    write_json(
        d / "report.json",
        {
            "$schema": f"{SCHEMAS}/item/report/definition/report/3.0.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": THEME,
                    "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"},
                    "type": "SharedResources",
                }
            },
            "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True},
        },
    )
    write_json(
        d / "pages" / "pages.json",
        {
            "$schema": f"{SCHEMAS}/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": list(PAGES),
            "activePageName": next(iter(PAGES)),
        },
    )
    for page, (title, visuals) in PAGES.items():
        write_json(
            d / "pages" / page / "page.json",
            {
                "$schema": f"{SCHEMAS}/item/report/definition/page/2.0.0/schema.json",
                "name": page,
                "displayName": title,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
        )
        for v in visuals:
            write_json(d / "pages" / page / "visuals" / v["name"] / "visual.json", v)
    theme_src = (
        Path(
            r"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\sharedresources"
            r"\BaseThemes"
        )
        / f"{THEME}.json"
    )
    theme_dst = rp / "StaticResources" / "SharedResources" / "BaseThemes" / f"{THEME}.json"
    if theme_src.exists():
        theme_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(theme_src, theme_dst)
    elif not theme_dst.exists():
        sys.exit(f"base theme {THEME} not found; open the report once in Power BI Desktop to write it")


def main() -> None:
    schemas = {m: pq.read_schema(EXPORTS / f"{m}.parquet") for m in MARTS}
    # Power BI names are case-insensitive: a measure may not share a name with another measure or with a column
    # of its table (Desktop refuses to load the model otherwise).
    measure_names = [m[1].lower() for m in MEASURES]
    clashes = {n for n in measure_names if measure_names.count(n) > 1}
    clashes |= {m[1] for m in MEASURES if m[1].lower() in {f.name.lower() for f in schemas[m[0]]}}
    if clashes:
        sys.exit(f"measure names clash with columns or each other: {sorted(clashes)}")
    semantic_model(schemas)
    report()
    write_json(
        OUT / f"{NAME}.pbip",
        {
            "$schema": f"{SCHEMAS}/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    print(
        f"wrote {OUT.relative_to(ROOT)}: {len(MARTS) + 2} tables, {len(MEASURES)} measures, "
        f"{sum(len(v) for _, v in PAGES.values())} visuals on {len(PAGES)} pages"
    )


if __name__ == "__main__":
    main()
