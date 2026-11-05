"""
RetailFinance - Power BI projesi (PBIP) üretici
Çalıştırma (proje klasöründen):  python powerbi/build_pbip.py
Çıktı: powerbi/pbip/RetailFinance.pbip  (+ .SemanticModel ve .Report klasörleri)

Model TMDL, rapor PBIR (Power BI'ın metin tabanlı proje biçimi) olarak yazılır.
Power BI Desktop'ta RetailFinance.pbip açılır, Giriş > Yenile ile veri SQL Server'dan yüklenir.
Her çalıştırmada pbip klasörünü baştan üretir; Desktop'ta yapılan elle değişiklikler silinir.
"""
import glob
import json
import shutil
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "pbip"
NAME = "RetailFinance"
SERVER = r"localhost\SQLEXPRESS"
DATABASE = "RetailFinance"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
V_REPORT, V_PAGE, V_VISUAL = "3.2.0", "2.1.0", "2.12.0"
THEME_GLOB = ("C:/Program Files/WindowsApps/Microsoft.MicrosoftPowerBIDesktop_*/bin/"
              "WebView2Resources/minerva/sharedresources/BaseThemes/CY*.json")

# ---------------------------------------------------------------------------
# 1) Tablolar: (Power BI adı, SQL nesnesi, [(kolon, tip)])
#    Tipler SQL INFORMATION_SCHEMA'dan: int/smallint/tinyint -> int64, float -> double,
#    varchar/nvarchar -> string, date/datetime2 -> dateTime, bit -> boolean
# ---------------------------------------------------------------------------
I, D, S, T, B = "int64", "double", "string", "dateTime", "boolean"
KEYS = [("company_key", I), ("ticker", S), ("short_name", S), ("date_key", I), ("period_label", S),
        ("fiscal_year", I), ("fiscal_quarter", I), ("year_quarter", S)]
TABLES = [
    ("dim_company", "dim_company", [("company_key", I), ("ticker", S), ("company_name", S), ("short_name", S),
                                    ("sector", S), ("financial_group", S), ("tms29_start_date", T),
                                    ("tms29_source", S)]),
    ("dim_date", "dim_date", [("date_key", I), ("period_end_date", T), ("fiscal_year", I), ("fiscal_quarter", I),
                              ("period_month", I), ("period_label", S), ("year_quarter", S), ("is_tms29_era", B)]),
    ("fact_ratios", "vw_ratios", KEYS + [("period_month", I), ("is_tms29", I)] + [(c, D) for c in [
        "revenue", "gross_profit", "core_operating_profit", "operating_profit", "ebitda", "net_income", "net_debt",
        "fcf", "gross_margin", "ebitda_margin", "core_operating_margin", "operating_margin", "net_margin",
        "current_ratio", "quick_ratio", "cash_ratio", "net_debt_to_ebitda", "fin_debt_to_equity",
        "liabilities_to_assets", "ebitda_to_finance_expense", "inventory_turnover", "dio", "dso", "dpo",
        "cash_conversion_cycle", "ocf_to_ebitda", "fcf_margin", "capex_to_revenue", "dupont_net_margin",
        "dupont_asset_turnover", "dupont_equity_multiplier", "roe_annualized", "roa_annualized"]]),
    ("fact_quarterly", "vw_quarterly_std", KEYS + [("is_tms29", I)] + [(c, D) for c in [
        "revenue_q", "gross_profit_q", "ebitda_q", "core_operating_profit_q", "net_income_q",
        "operating_cash_flow_q", "capex_q", "gross_margin_q", "ebitda_margin_q", "net_margin_q",
        "revenue_qoq_nominal", "revenue_yoy_nominal"]] + [("known_issue_flag", I), ("qoq_basis_ok", I),
                                                           ("yoy_basis_ok", I)]),
    ("fact_growth", "vw_growth_ytd", KEYS + [("is_tms29", I), ("revenue_ytd", D), ("revenue_ytd_prev_year", D),
                                             ("revenue_growth_nominal", D), ("ebitda_growth_nominal", D),
                                             ("comparability", S)]),
    ("known_issues", "known_data_issues", [("issue_id", I), ("ticker", S), ("period_label", S), ("scope", S),
                                           ("severity", S), ("status", S), ("description", S), ("evidence", S)]),
    ("dq_results", "dq_results", [("result_id", I), ("run_at", T), ("test_name", S), ("ticker", S),
                                  ("period_label", S), ("result", S), ("detail", S)]),
]
FACTS = ["fact_ratios", "fact_quarterly", "fact_growth"]

# ---------------------------------------------------------------------------
# 2) Ölçüler: (ad, DAX, biçim, klasör)
#    Kural: seçili dönem önce VAR'a alınır; CALCULATE filtresinde ölçü çağrılmaz.
# ---------------------------------------------------------------------------
PCT, RATIO, MULT, DAYS, BN, INT = "0.0%", "0.00", '0.00"x"', "0.0", "#,##0.0", "0"


def at_period(expr):
    return f"VAR _d = [Selected Date Key]\nRETURN\n    CALCULATE ( {expr}, dim_date[date_key] = _d )"


M = []


def m(name, dax, fmt=None, folder=None):
    M.append((name, dax, fmt, folder))


m("Selected Date Key", "MAX ( dim_date[date_key] )", INT, "0 Dönem")
m("Selected Index", "MAX ( dim_date[period_index] )", INT, "0 Dönem")
m("Selected Period", "VAR _d = [Selected Date Key]\nRETURN\n    LOOKUPVALUE ( dim_date[period_label], dim_date[date_key], _d )",
  None, "0 Dönem")

for nm, col in [("Revenue YTD", "revenue"), ("Gross Profit YTD", "gross_profit"), ("EBITDA YTD", "ebitda"),
                ("Net Income YTD", "net_income"), ("Net Debt", "net_debt"), ("Free Cash Flow YTD", "fcf")]:
    m(nm, at_period(f"SUM ( fact_ratios[{col}] )"), "#,##0", "1 Büyüklükler")
m("Revenue YTD (TL bn)", "DIVIDE ( [Revenue YTD], 1000000000 )", BN, "1 Büyüklükler")

AVG = [  # (ad, kolon, biçim, klasör)
    ("Gross Margin", "gross_margin", PCT, "2 Kârlılık"),
    ("EBITDA Margin", "ebitda_margin", PCT, "2 Kârlılık"),
    ("Core Operating Margin", "core_operating_margin", PCT, "2 Kârlılık"),
    ("Net Margin", "net_margin", PCT, "2 Kârlılık"),
    ("Current Ratio", "current_ratio", RATIO, "3 Likidite"),
    ("Quick Ratio", "quick_ratio", RATIO, "3 Likidite"),
    ("Cash Ratio", "cash_ratio", RATIO, "3 Likidite"),
    ("Net Debt to EBITDA", "net_debt_to_ebitda", MULT, "4 Borçluluk"),
    ("Liabilities to Assets", "liabilities_to_assets", PCT, "4 Borçluluk"),
    ("EBITDA to Finance Expense", "ebitda_to_finance_expense", MULT, "4 Borçluluk"),
    ("Inventory Turnover", "inventory_turnover", RATIO, "5 Çalışma sermayesi ve nakit"),
    ("DIO (days)", "dio", DAYS, "5 Çalışma sermayesi ve nakit"),
    ("DSO (days)", "dso", DAYS, "5 Çalışma sermayesi ve nakit"),
    ("DPO (days)", "dpo", DAYS, "5 Çalışma sermayesi ve nakit"),
    ("Cash Conversion Cycle (days)", "cash_conversion_cycle", DAYS, "5 Çalışma sermayesi ve nakit"),
    ("OCF to EBITDA", "ocf_to_ebitda", RATIO, "5 Çalışma sermayesi ve nakit"),
    ("FCF Margin", "fcf_margin", PCT, "5 Çalışma sermayesi ve nakit"),
    ("Capex to Revenue", "capex_to_revenue", PCT, "5 Çalışma sermayesi ve nakit"),
    ("DuPont Net Margin", "dupont_net_margin", PCT, "6 DuPont"),
    ("DuPont Asset Turnover", "dupont_asset_turnover", RATIO, "6 DuPont"),
    ("DuPont Equity Multiplier", "dupont_equity_multiplier", RATIO, "6 DuPont"),
    ("ROE (annualized)", "roe_annualized", PCT, "6 DuPont"),
    ("ROA (annualized)", "roa_annualized", PCT, "6 DuPont"),
]
for nm, col, fmt, folder in AVG:
    m(nm, at_period(f"AVERAGE ( fact_ratios[{col}] )"), fmt, folder)
# Negatif özkaynakta oran negatif çıkar ve anlamsızdır (ROE gibi boş bırakılır)
m("Fin Debt to Equity",
  "VAR _d = [Selected Date Key]\nVAR _v = CALCULATE ( AVERAGE ( fact_ratios[fin_debt_to_equity] ), dim_date[date_key] = _d )\nRETURN\n    IF ( _v < 0, BLANK (), _v )",
  MULT, "4 Borçluluk")

for base, fmt in [("Gross Margin", PCT), ("EBITDA Margin", PCT), ("Net Margin", PCT), ("Current Ratio", RATIO)]:
    m(f"Sector Avg {base}", f"CALCULATE ( [{base}], ALL ( dim_company ) )", fmt, "7 Sektör")
m("Gross Margin vs Sector (pp)", "[Gross Margin] - [Sector Avg Gross Margin]", PCT, "7 Sektör")
m("EBITDA Margin vs Sector (pp)", "[EBITDA Margin] - [Sector Avg EBITDA Margin]", PCT, "7 Sektör")
m("Net Margin vs Sector (pp)", "[Net Margin] - [Sector Avg Net Margin]", PCT, "7 Sektör")
m("Current Ratio vs Sector", "[Current Ratio] - [Sector Avg Current Ratio]", RATIO, "7 Sektör")


def rank(name, measure, order):
    m(name, f"IF (\n    NOT ISBLANK ( [{measure}] ),\n    RANKX (\n        FILTER ( ALL ( dim_company[short_name] ), NOT ISBLANK ( [{measure}] ) ),\n        [{measure}], , {order}, DENSE\n    )\n)",
      INT, "7 Sektör")


rank("Gross Margin Rank", "Gross Margin", "DESC")
rank("EBITDA Margin Rank", "EBITDA Margin", "DESC")
rank("Net Margin Rank", "Net Margin", "DESC")
rank("Leverage Rank (1 = lowest)", "Net Debt to EBITDA", "ASC")
rank("Cash Conversion Rank", "OCF to EBITDA", "DESC")

m("Revenue Q", "SUM ( fact_quarterly[revenue_q] )", "#,##0", "8 Çeyreklik (nominal)")
m("EBITDA Q", "SUM ( fact_quarterly[ebitda_q] )", "#,##0", "8 Çeyreklik (nominal)")
m("Net Income Q", "SUM ( fact_quarterly[net_income_q] )", "#,##0", "8 Çeyreklik (nominal)")
m("EBITDA Margin Q", "DIVIDE ( [EBITDA Q], [Revenue Q] )", PCT, "8 Çeyreklik (nominal)")
m("Revenue QoQ (nominal)",
  "VAR _idx = [Selected Index]\nVAR _cur = [Revenue Q]\nVAR _prev =\n    CALCULATE ( [Revenue Q], FILTER ( ALL ( dim_date ), dim_date[period_index] = _idx - 1 ) )\nRETURN\n    IF ( ISBLANK ( _prev ) || ISBLANK ( _cur ), BLANK (), DIVIDE ( _cur, _prev ) - 1 )",
  PCT, "8 Çeyreklik (nominal)")
for nm, col in [("Revenue TTM (nominal)", "revenue_q"), ("EBITDA TTM (nominal)", "ebitda_q")]:
    m(nm, f"VAR _idx = [Selected Index]\nRETURN\n    CALCULATE (\n        SUM ( fact_quarterly[{col}] ),\n        FILTER ( ALL ( dim_date ), dim_date[period_index] > _idx - 4 && dim_date[period_index] <= _idx )\n    )",
      "#,##0", "8 Çeyreklik (nominal)")
m("Quarter Basis OK",
  "VAR _d = [Selected Date Key]\nRETURN\n    IF ( CALCULATE ( MIN ( fact_quarterly[qoq_basis_ok] ), dim_date[date_key] = _d ) = 1, 1, 0 )",
  INT, "8 Çeyreklik (nominal)")

m("Revenue YTD PY",
  "VAR _d = [Selected Date Key]\nRETURN\n    CALCULATE ( SUM ( fact_ratios[revenue] ), ALL ( dim_date ), dim_date[date_key] = _d - 100 )",
  "#,##0", "9 Büyüme (nominal)")
m("Revenue Growth YoY (nominal)",
  "VAR _cy = [Revenue YTD]\nVAR _py = [Revenue YTD PY]\nRETURN\n    IF ( ISBLANK ( _py ) || ISBLANK ( _cy ), BLANK (), DIVIDE ( _cy, _py ) - 1 )", PCT, "9 Büyüme (nominal)")
m("Growth Comparability",
  "VAR _d = [Selected Date Key]\nVAR _break =\n    CALCULATE ( COUNTROWS ( fact_growth ), fact_growth[comparability] = \"BASE_BREAK\", dim_date[date_key] = _d )\nRETURN\n    IF ( _break > 0, \"BASE_BREAK\", IF ( _d >= 202312, \"NOMINAL_TMS29\", \"NOMINAL\" ) )",
  None, "9 Büyüme (nominal)")
m("Growth Font Color",
  "IF ( [Growth Comparability] = \"BASE_BREAK\", \"#B3B3B3\", \"#252423\" )", None, "9 Büyüme (nominal)")

m("TMS29 Banner",
  "IF (\n    [Selected Date Key] >= 202312,\n    \"TMS 29 dönemi: dönemler arası büyüme ve çeyreklik farklar nominal\",\n    \"TMS 29 öncesi dönem: değerler nominal TL\"\n)",
  None, "A Uyarılar")
m("Known Issue Count",
  "VAR _p = [Selected Period]\nRETURN\n    CALCULATE (\n        COUNTROWS ( known_issues ),\n        TREATAS ( VALUES ( dim_company[ticker] ), known_issues[ticker] ),\n        known_issues[period_label] = _p\n    )",
  INT, "A Uyarılar")
m("Data Issue Banner",
  "IF (\n    [Known Issue Count] > 0,\n    \"UYARI: Seçili şirket/dönem için kaynak veride bilinen bir sorun var (known_issues).\",\n    \"Seçili şirket/dönem için kayıtlı kaynak veri sorunu yok.\"\n)",
  None, "A Uyarılar")
m("Growth Banner",
  "SWITCH (\n    [Growth Comparability],\n    \"BASE_BREAK\", \"Büyüme karşılaştırması güvenilir değil (kaynakta baz kırılması); gri gösterilir.\",\n    \"NOMINAL_TMS29\", \"Büyüme nominal TL'dir; reel büyüme değildir.\",\n    \"Büyüme nominal TL'dir.\"\n)",
  None, "A Uyarılar")
m("Blank Ratio Note",
  "\"Boş oran = anlamsız: FAVÖK marjı %1'in altında ya da özkaynak sıfır/negatif\"",
  None, "A Uyarılar")
m("Footnotes",
  "\"Kaynak: İş Yatırım (isyatirimhisse, resmî olmayan kaynak); kritik rakamlar KAP ile doğrulanmalı. \" & \"TMS 29 (2023/12 ve sonrası): kolonlar arası büyüme ve çeyreklik farklar nominaldir; marj, likidite ve kaldıraç aynı dönem kolonu içinde hesaplandığı için etkilenmez. \" & \"2022/12, 2025/9 ve 2025/12 kolonlarında kaynak veride baz kırılması var (dw.known_data_issues).\"",
  None, "A Uyarılar")

m("DQ Total Checks", "COUNTROWS ( dq_results )", INT, "B Veri kalitesi")
for nm, res in [("DQ Pass", "PASS"), ("DQ Explained", "EXPLAINED"), ("DQ Fail", "FAIL")]:
    m(nm, f"VAR _n = CALCULATE ( COUNTROWS ( dq_results ), dq_results[result] = \"{res}\" )\nRETURN\n    IF ( ISBLANK ( _n ), 0, _n )",
      INT, "B Veri kalitesi")
m("DQ Pass or Explained %", "DIVIDE ( [DQ Pass] + [DQ Explained], [DQ Total Checks] )", PCT, "B Veri kalitesi")


# KPI kartlarının hedefi: aynı ölçünün bir yıl önceki (aynı ay) değeri. Oran aynı kolon içinde
# hesaplandığı için karşılaştırma TMS 29'dan etkilenmez; TL tutarlar için hedef kullanılmaz.
for nm, col in [("Gross Margin", "gross_margin"), ("EBITDA Margin", "ebitda_margin"), ("Net Margin", "net_margin"),
                ("ROE (annualized)", "roe_annualized"), ("Net Debt to EBITDA", "net_debt_to_ebitda"),
                ("Current Ratio", "current_ratio"), ("Quick Ratio", "quick_ratio"), ("Cash Ratio", "cash_ratio"),
                ("OCF to EBITDA", "ocf_to_ebitda"), ("Cash Conversion Cycle (days)", "cash_conversion_cycle"),
                ("Liabilities to Assets", "liabilities_to_assets")]:
    fmt = next((x[2] for x in M if x[0] == nm), None)
    m(f"{nm} PY",
      f"VAR _d = [Selected Date Key]\nRETURN\n    CALCULATE ( AVERAGE ( fact_ratios[{col}] ), ALL ( dim_date ), dim_date[date_key] = _d - 100 )",
      fmt, "C Önceki yıl (KPI hedefi)")
m("DQ Summary",
  "[DQ Total Checks] & \" test · \" & [DQ Pass] & \" PASS · \" & [DQ Explained] & \" açıklanmış · \" & [DQ Fail] & \" FAIL\"",
  None, "B Veri kalitesi")

MEASURE_NAMES = {x[0] for x in M}


# ---------------------------------------------------------------------------
# 3) TMDL yazımı
# ---------------------------------------------------------------------------
def q(name):  # TMDL ad tırnaklama
    return name if name.replace("_", "").isalnum() else "'" + name.replace("'", "''") + "'"


TAGS = []


def tag():  # deterministik lineageTag (her üretimde aynı)
    TAGS.append(1)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NAME}-{len(TAGS)}"))


def expr_block(text, indent):
    pad = "\t" * indent
    return "\n".join(pad + line for line in text.split("\n"))


def m_partition(pbi, sql_obj):
    return (f"\tpartition {pbi} = m\n\t\tmode: import\n\t\tsource =\n"
            f"\t\t\t\tlet\n"
            f"\t\t\t\t    Source = Sql.Database(\"{SERVER}\", \"{DATABASE}\"),\n"
            f"\t\t\t\t    Data = Source{{[Schema=\"dw\",Item=\"{sql_obj}\"]}}[Data]\n"
            f"\t\t\t\tin\n\t\t\t\t    Data\n")


def table_tmdl(pbi, sql_obj, cols):
    out = [f"table {pbi}", f"\tlineageTag: {tag()}", ""]
    for c, t in cols:
        out.append(f"\tcolumn {c}")
        out.append(f"\t\tdataType: {t}")
        if t == "double":
            out.append("\t\tformatString: 0.0000")
        out.append(f"\t\tlineageTag: {tag()}")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {c}")
        if pbi == "dim_date" and c == "period_label":
            out.append("\t\tsortByColumn: date_key")
        if c in ("company_key",) or (c.endswith("_key") and pbi.startswith("fact")):
            out.append("\t\tisHidden")
        out.append("")
    if pbi == "dim_date":
        out += ["\tcolumn period_index = dim_date[fiscal_year] * 4 + dim_date[fiscal_quarter]",
                "\t\tdataType: int64", "\t\tformatString: 0", f"\t\tlineageTag: {tag()}",
                "\t\tsummarizeBy: none", ""]
    out.append(m_partition(pbi, sql_obj))
    return "\n".join(out)


def measures_tmdl():
    out = ["table _Measures", f"\tlineageTag: {tag()}", ""]
    for name, dax, fmt, folder in M:
        if "\n" in dax:
            out.append(f"\tmeasure {q(name)} =")
            out.append(expr_block(dax, 3))
        else:
            out.append(f"\tmeasure {q(name)} = {dax}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if folder:
            out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tag()}")
        out.append("")
    out += ["\tcolumn Dummy", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag()}",
            "\t\tsummarizeBy: none", "\t\tsourceColumn: Dummy", "",
            "\tpartition _Measures = m", "\t\tmode: import", "\t\tsource =",
            "\t\t\t\tlet", "\t\t\t\t    Source = #table(type table [Dummy = text], {})",
            "\t\t\t\tin", "\t\t\t\t    Source", ""]
    return "\n".join(out)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path, obj):
    write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def build_model(root):
    sm = root / f"{NAME}.SemanticModel"
    write_json(sm / "definition.pbism", {
        "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}})
    d = sm / "definition"
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    order = [t[0] for t in TABLES] + ["_Measures"]
    write(d / "model.tmdl",
          "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
          "\tsourceQueryCulture: tr-TR\n\tdataAccessOptions\n\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
          f"annotation PBI_QueryOrder = {json.dumps(order)}\n\n"
          "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
          + "".join(f"ref table {q(t)}\n" for t in order))
    for pbi, sql_obj, cols in TABLES:
        write(d / "tables" / f"{pbi}.tmdl", table_tmdl(pbi, sql_obj, cols))
    write(d / "tables" / "_Measures.tmdl", measures_tmdl())
    rel = []
    for f in FACTS:
        for dim, key in [("dim_company", "company_key"), ("dim_date", "date_key")]:
            rel.append(f"relationship {f}_{key}\n\tfromColumn: {f}.{key}\n\ttoColumn: {dim}.{key}\n")
    write(d / "relationships.tmdl", "\n".join(rel))


# ---------------------------------------------------------------------------
# 4) Rapor (PBIR) - koyu lacivert tasarım (docs/ tasarım mockup'ı ile aynı dil)
# ---------------------------------------------------------------------------
BG, SIDE, CARD, LINE, INK, MUTE = "#0C1636", "#101C42", "#15234C", "#26386B", "#EDF2FC", "#A3B2D1"
ACTIVE = "#23408F"
# Şirket renkleri: Power BI kategorileri alfabetik sıralar (BİM, CarrefourSA, Migros, Şok)
DATA_COLORS = ["#5B9BFF", "#C49BFF", "#FFA94D", "#3DD6C3", "#FFD166", "#FF8A8A", "#4ADE80", "#9AAACB"]
METRIC_COLORS = {"Gross Margin": "#5B9BFF", "EBITDA Margin": "#3DD6C3", "Net Margin": "#FFD166",
                 "DIO (days)": "#5B9BFF", "DSO (days)": "#3DD6C3", "DPO (days)": "#FFA94D",
                 "Cash Conversion Cycle (days)": "#EDF2FC", "OCF to EBITDA": "#C49BFF", "FCF Margin": "#FFD166"}
THEME_NAME = "RetailFinanceDark"


def theme_json():
    s = lambda c: {"solid": {"color": c}}
    no_box = {"background": [{"show": False}], "border": [{"show": False}], "dropShadow": [{"show": False}],
              "title": [{"show": False}]}
    return {
        "name": THEME_NAME,
        "dataColors": DATA_COLORS,
        "background": CARD, "foreground": INK, "tableAccent": "#5B9BFF",
        "good": "#4ADE80", "bad": "#FF8A8A", "neutral": "#FFC58A",
        "textClasses": {
            "callout": {"fontSize": 22, "fontFace": "Segoe UI Semibold", "color": INK},
            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": INK},
            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": INK},
            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": MUTE},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": s(CARD), "transparency": 0}],
                "border": [{"show": True, "color": s(LINE), "radius": 12}],
                "dropShadow": [{"show": False}],
                "title": [{"show": True, "fontColor": s(INK), "fontSize": 11, "fontFamily": "Segoe UI Semibold"}],
                "categoryAxis": [{"labelColor": s(MUTE), "titleColor": s(MUTE), "showAxisTitle": False,
                                  "gridlineShow": False}],
                "valueAxis": [{"labelColor": s(MUTE), "titleColor": s(MUTE), "showAxisTitle": False,
                               "gridlineColor": s("#1A2850")}],
                "legend": [{"show": True, "position": "Top", "labelColor": s(MUTE), "showTitle": False}],
                "labels": [{"color": s("#C9D3EA")}],
            }},
            "page": {"*": {"background": [{"color": s(BG), "transparency": 0}],
                           "outspace": [{"color": s("#070D1F"), "transparency": 0}]}},
            "card": {"*": {"labels": [{"color": s(INK)}], "categoryLabels": [{"color": s(MUTE)}]}},
            "kpi": {"*": {"title": [{"show": True, "fontColor": s(MUTE), "fontSize": 9}]}},
            "slicer": {"*": {"items": [{"fontColor": s(INK), "background": s(CARD)}],
                             "header": [{"fontColor": s(MUTE)}]}},
            "tableEx": {"*": {
                "columnHeaders": [{"fontColor": s(MUTE), "backColor": s(CARD)}],
                "values": [{"fontColorPrimary": s(INK), "backColorPrimary": s(CARD),
                            "fontColorSecondary": s(INK), "backColorSecondary": s("#0F1A38")}],
                "grid": [{"gridVertical": False, "gridHorizontal": True, "gridHorizontalColor": s(LINE),
                          "outlineColor": s(LINE)}],
                "total": [{"totals": False}],
            }},
            "textbox": {"*": no_box},
            "actionButton": {"*": no_box},
            "shape": {"*": {"background": [{"show": False}], "border": [{"show": False}],
                            "dropShadow": [{"show": False}], "title": [{"show": False}]}},
        },
    }


def lit(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, int):
        s = f"{v}L"
    elif isinstance(v, float):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def num(v):  # biçim özellikleri için sayı (D)
    return {"expr": {"Literal": {"Value": f"{v}D"}}}


def solid(c):
    return {"solid": {"color": lit(c)}}


def props(**kw):
    return [{"properties": {k: (num(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else lit(v))
                            for k, v in kw.items()}}]


def fld(ref):
    """'Measure Name' -> ölçü, 'table.column' -> kolon"""
    if ref in MEASURE_NAMES:
        return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": ref}}, f"_Measures.{ref}"
    t, c = ref.split(".", 1)
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}, ref


LABELS = {"dim_company.short_name": "Şirket", "dim_date.period_label": "Dönem"}


def proj(ref, display=None):
    display = display or LABELS.get(ref)
    f, qr = fld(ref)
    p = {"field": f, "queryRef": qr, "nativeQueryRef": qr.split(".", 1)[1]}
    if display:
        p["displayName"] = display
    return p


def year_end_filter(name):
    """Görsel filtresi: yalnız yıl sonu (12. ay) dönemleri"""
    return {"filters": [{"name": name, "type": "Categorical",
                         "field": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_date"}},
                                              "Property": "period_month"}},
                         "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}],
                                    "Where": [{"Condition": {"In": {
                                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                                    "Property": "period_month"}}],
                                        "Values": [[{"Literal": {"Value": "12L"}}]]}}}]}}]}


def metric_colors(measures):
    out = []
    for mname in measures:
        if mname in METRIC_COLORS:
            out.append({"properties": {"fill": {"solid": {"color": lit(METRIC_COLORS[mname])}}},
                        "selector": {"metadata": f"_Measures.{mname}"}})
    return out


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals, self.no_filter = name, display, [], []

    def add(self, vname, vtype, x, y, w, h, roles=None, title=None, objects=None, sort=None, extra=None,
            container=None, filters=None):
        roles = roles or {}
        assert len(vname) <= 50 and all(r in MEASURE_NAMES or "." in r for v in roles.values() for r in
                                         [p if isinstance(p, str) else p[0] for p in v]), vname
        visual = {"visualType": vtype}
        if roles:
            qs = {role: {"projections": [proj(*(r if isinstance(r, tuple) else (r,))) for r in refs]}
                  for role, refs in roles.items()}
            visual["query"] = {"queryState": qs}
            if sort:
                f, _ = fld(sort[0])
                visual["query"]["sortDefinition"] = {"sort": [{"field": f, "direction": sort[1]}],
                                                     "isDefaultSort": False}
            visual["drillFilterOtherVisuals"] = True
        if vtype == "tableEx":  # toplam satırı oranlarda anlamsız
            objects = dict(objects or {}, total=props(totals=False))
        if objects:
            visual["objects"] = objects
        vco = dict(container or {})
        if title:
            vco["title"] = props(show=True, text=title)
        if vco:
            visual["visualContainerObjects"] = vco
        if extra:
            visual.update(extra)
        v = {"$schema": f"{SCHEMA}/item/report/definition/visualContainer/{V_VISUAL}/schema.json",
             "name": vname,
             "position": {"x": x, "y": y, "z": len(self.visuals) * 1000, "height": h, "width": w,
                          "tabOrder": len(self.visuals) * 1000},
             "visual": visual}
        if filters:
            v["filterConfig"] = filters
        self.visuals.append(v)
        return vname


# --- yapı taşları ----------------------------------------------------------
def textbox(pg, vname, x, y, w, h, paragraphs):
    """paragraphs: [[(metin, {stil}), ...], ...]"""
    paras = [{"textRuns": [{"value": t, "textStyle": st} for t, st in runs]} for runs in paragraphs]
    return pg.add(vname, "textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paras}}]})


DEFAULT = {"id": "default"}


def stated(props_dict):  # yeni şekil/buton görselleri biçimi durum seçicisiyle bekler
    return [{"properties": props_dict, "selector": DEFAULT}]


def rect(pg, vname, x, y, w, h, color):
    return pg.add(vname, "shape", x, y, w, h, objects={
        "shape": props(tileShape="rectangle"),
        "fill": stated({"show": lit(True), "fillColor": solid(color), "transparency": num(0)}),
        "outline": stated({"show": lit(False)})})


def nav_button(pg, vname, x, y, label, target, active):
    return pg.add(vname, "actionButton", x, y, 160, 40, objects={
        "icon": [{"properties": {"show": lit(False)}}],
        # aç/kapa anahtarı seçicisiz, stil özellikleri 'default' durum seçicisiyle yazılır
        "text": [{"properties": {"show": lit(True)}},
                 {"properties": {"text": lit(label), "fontColor": solid("#FFFFFF" if active else MUTE),
                                 "fontSize": num(10), "bold": lit(active), "horizontalAlignment": lit("left"),
                                 "leftMargin": num(14)}, "selector": DEFAULT}],
        "fill": [{"properties": {"show": lit(active)}},
                 {"properties": {"fillColor": solid(ACTIVE), "transparency": num(0)}, "selector": DEFAULT}],
        "outline": [{"properties": {"show": lit(False)}}],
    }, container={"visualLink": [{"properties": {"show": lit(True), "type": lit("PageNavigation"),
                                                  "navigationSection": lit(target)}}]})


def card(pg, vname, measure, x, y, w, h, display=None, text=False, size=None, title=None):
    obj = {"labels": [{"properties": {"fontSize": num(size or (9 if text else 20)), "color": solid(INK)}}]}
    if text:
        obj["categoryLabels"] = props(show=False)
        obj["wordWrap"] = props(show=True)
    return pg.add(vname, "card", x, y, w, h, {"Values": [(measure, display) if display else measure]},
                  objects=obj, title=title)


def kpi(pg, vname, measure, x, y, w, h, title, goal=None, low_is_good=False):
    roles = {"Indicator": [measure], "TrendLine": ["dim_date.period_label"]}
    if goal:
        roles["Goal"] = [goal]
    obj = {"indicator": [{"properties": {"fontSize": num(20), "fontColor": solid(INK)}}],
           "trendline": props(show=True, transparency=40),
           "goals": props(showGoal=bool(goal), showDistance=bool(goal), goalText="Geçen yıl",
                          distanceLabel="Value")}
    if low_is_good:
        obj["status"] = props(direction="Negative")
    name = pg.add(vname, "kpi", x, y, w, h, roles, title=title, objects=obj,
                  sort=("dim_date.period_label", "Ascending"), filters=year_end_filter(f"{vname}_ye"))
    pg.no_filter.append(name)
    return name


def line_chart(pg, vname, x, y, w, h, measures, title, series=None, year_end=True):
    roles = {"Category": ["dim_date.period_label"], "Y": measures}
    if series:
        roles["Series"] = [series]
    objs = {"lineStyles": props(strokeWidth=3)}
    dp = metric_colors([m if isinstance(m, str) else m[0] for m in measures]) if not series else []
    if dp:
        objs["dataPoint"] = dp
    name = pg.add(vname, "lineChart", x, y, w, h, roles, title=title, objects=objs,
                  sort=("dim_date.period_label", "Ascending"),
                  filters=year_end_filter(f"{vname}_ye") if year_end else None)
    pg.no_filter.append(name)
    return name


def sidebar(pg, active):
    rect(pg, f"{pg.name}_side_bg", 0, 0, 184, 720, SIDE)
    textbox(pg, f"{pg.name}_logo", 16, 16, 160, 52, [
        [("BIST Perakende", {"fontWeight": "bold", "fontSize": "13pt", "color": INK})],
        [("Finansal Performans", {"fontSize": "9pt", "color": MUTE})]])
    for i, (label, target) in enumerate([("Sektör Özeti", "p1_sector"), ("Şirket Detayı", "p2_company"),
                                         ("Likidite ve Borç", "p3_liquidity")]):
        nav_button(pg, f"{pg.name}_nav{i}", 12, 84 + i * 48, label, target, target == active)
    card(pg, f"{pg.name}_dq", "DQ Summary", 12, 560, 160, 92, text=True, size=9, title="Veri kalitesi")
    textbox(pg, f"{pg.name}_src", 12, 660, 160, 48, [
        [("Kaynak: İş Yatırım (resmî değil), KAP ile teyit edilmeli", {"fontSize": "8pt", "color": MUTE})]])


def header(pg, title, subtitle, banner_measure, company_single=False, default=None):
    textbox(pg, f"{pg.name}_title", 196, 4, 520, 60, [
        [(title, {"fontWeight": "bold", "fontSize": "16pt", "color": INK})],
        [(subtitle, {"fontSize": "9pt", "color": MUTE})]])
    obj = {"data": props(mode="Dropdown"), "selection": props(singleSelect=company_single)}
    if default:
        obj["general"] = [{"properties": {"filter": {"filter": {
            "Version": 2, "From": [{"Name": "d", "Entity": "dim_company", "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "short_name"}}],
                "Values": [[{"Literal": {"Value": f"'{default}'"}}]]}}}]}}}}]
    extra = None if company_single else {"syncGroup": {"groupName": "company", "fieldChanges": True,
                                                       "filterChanges": True}}
    pg.add(f"{pg.name}_slc_company", "slicer", 724, 4, 170, 62, {"Values": ["dim_company.short_name"]},
           objects=obj, extra=extra)
    pg.period = pg.add(f"{pg.name}_slc_period", "slicer", 902, 4, 150, 62, {"Values": ["dim_date.period_label"]},
                       objects={"data": props(mode="Dropdown"), "selection": props(singleSelect=True)},
                       extra={"syncGroup": {"groupName": "period", "fieldChanges": True, "filterChanges": True}})
    card(pg, f"{pg.name}_banner", banner_measure, 1060, 4, 208, 62, text=True, size=8)


def footer(pg):
    st = {"fontSize": "8pt", "color": MUTE}
    textbox(pg, f"{pg.name}_footnotes", 196, 668, 1072, 46, [
        [("Kaynak: İş Yatırım (isyatirimhisse, resmî olmayan kaynak); kritik rakamlar KAP ile doğrulanmalı. ", st),
         ("TMS 29 (2023/12 ve sonrası): ", {"fontSize": "8pt", "color": "#FFC58A"}),
         ("dönemler arası büyüme ve çeyreklik farklar nominaldir; marj, likidite ve kaldıraç aynı dönem kolonu "
          "içinde hesaplandığı için etkilenmez. 2022/12, 2025/9 ve 2025/12 kolonlarında kaynakta baz kırılması var.", st)]])


KX = [196 + i * 180 for i in range(6)]  # KPI kartı x konumları (genişlik 172)


def build_pages():
    pages = []

    # --- Sayfa 1: Sektör özeti ---
    p = Page("p1_sector", "Sektör Özeti")
    sidebar(p, p.name)
    header(p, "Sektör Özeti", "4 BIST perakendecisi · oranlar aynı dönem kolonu içinde · kartlar: yıl sonu trendi",
           "TMS29 Banner")
    for i, (mn, t, goal, low) in enumerate([
            ("Revenue YTD (TL bn)", "Hasılat YTD (mlr TL, nominal)", None, False),
            ("Gross Margin", "Ort. brüt marj", "Gross Margin PY", False),
            ("EBITDA Margin", "Ort. FAVÖK marjı", "EBITDA Margin PY", False),
            ("Net Margin", "Ort. net marj", "Net Margin PY", False),
            ("Net Debt to EBITDA", "Ort. net borç / FAVÖK", "Net Debt to EBITDA PY", True),
            ("OCF to EBITDA", "Ort. FNA / FAVÖK", "OCF to EBITDA PY", False)]):
        kpi(p, f"p1_kpi{i}", mn, KX[i], 70, 172, 104, t, goal, low)
    p.add("p1_margins", "clusteredBarChart", 196, 184, 356, 232,
          {"Category": ["dim_company.short_name"],
           "Y": [("Gross Margin", "Brüt marj"), ("EBITDA Margin", "FAVÖK marjı"), ("Net Margin", "Net marj")]},
          title="Marj karşılaştırması (seçili dönem)",
          objects={"dataPoint": metric_colors(["Gross Margin", "EBITDA Margin", "Net Margin"]),
                   "labels": props(show=True, fontSize=8)})
    line_chart(p, "p1_ebitda_trend", 562, 184, 440, 232, [("EBITDA Margin", "FAVÖK marjı")],
               "FAVÖK marjı trendi · yıl sonu", series="dim_company.short_name")
    textbox(p, "p1_insights", 1012, 184, 256, 232, [
        [("Öne çıkanlar · 2025/12", {"fontWeight": "bold", "fontSize": "11pt", "color": INK})],
        [("", {"fontSize": "4pt"})],
        [("BİM ", {"fontWeight": "bold", "fontSize": "8.5pt", "color": "#5B9BFF"}),
         ("en ince brüt marjla (%19,3) en yüksek ROE'yi (%11,2) üretiyor; getiri varlık devrinden (2,13x) geliyor.",
          {"fontSize": "8.5pt", "color": INK})],
        [("", {"fontSize": "4pt"})],
        [("Migros ", {"fontWeight": "bold", "fontSize": "8.5pt", "color": "#FFA94D"}),
         ("en yüksek FAVÖK marjını (%6,6) en düşük kaldıraçla (0,14x) taşıyor.", {"fontSize": "8.5pt", "color": INK})],
        [("", {"fontSize": "4pt"})],
        [("CarrefourSA ", {"fontWeight": "bold", "fontSize": "8.5pt", "color": "#C49BFF"}),
         ("net borç/FAVÖK 5,46x ve negatif özkaynakla sektörün en zayıf bilançosu.", {"fontSize": "8.5pt", "color": INK})],
        ])
    p.add("p1_table", "tableEx", 196, 426, 700, 232,
          {"Values": ["dim_company.short_name", ("Revenue YTD (TL bn)", "Hasılat (mlr TL)"),
                      ("Revenue Growth YoY (nominal)", "Büyüme YoY (nominal)"),
                      ("Growth Comparability", "Karşılaştırılabilirlik"),
                      ("EBITDA Margin", "FAVÖK marjı"), ("Net Margin", "Net marj"), ("ROE (annualized)", "ROE"),
                      ("OCF to EBITDA", "FNA / FAVÖK")]},
          title="Şirket karşılaştırması (seçili dönem) · gri büyüme = baz kırılması",
          objects={"values": [{"properties": {"fontColor": {"solid": {"color": {"expr": {"Measure": {
              "Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "Growth Font Color"}}}}}},
              "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                           "metadata": "_Measures.Revenue Growth YoY (nominal)"}}]})
    p.add("p1_share", "donutChart", 906, 426, 362, 232,
          {"Category": ["dim_company.short_name"], "Y": [("Revenue YTD (TL bn)", "Hasılat (mlr TL)")]},
          title="Sektör hasılat payı (seçili dönem)",
          objects={"labels": props(show=True, labelStyle="Percent of total"), "centerValue": props(show=False),
                   "legend": props(show=True, position="Right")})
    footer(p)
    pages.append(p)

    # --- Sayfa 2: Şirket detayı ---
    p = Page("p2_company", "Şirket Detayı")
    sidebar(p, p.name)
    header(p, "Şirket Detayı", "Yıl sonu trendleri 2019–2025 · kartlar geçen yılın aynı dönemiyle karşılaştırılır",
           "TMS29 Banner", company_single=True, default="BİM")
    for i, (mn, t, goal, low) in enumerate([
            ("Revenue YTD (TL bn)", "Hasılat YTD (mlr TL, nominal)", None, False),
            ("Gross Margin", "Brüt marj", "Gross Margin PY", False),
            ("EBITDA Margin", "FAVÖK marjı", "EBITDA Margin PY", False),
            ("Net Margin", "Net marj", "Net Margin PY", False),
            ("ROE (annualized)", "ROE (yıllık)", "ROE (annualized) PY", False),
            ("Cash Conversion Cycle (days)", "Nakit çevrim süresi (gün)", "Cash Conversion Cycle (days) PY", True)]):
        kpi(p, f"p2_kpi{i}", mn, KX[i], 70, 172, 104, t, goal, low)
    line_chart(p, "p2_margins", 196, 184, 440, 232,
               [("Gross Margin", "Brüt"), ("EBITDA Margin", "FAVÖK"), ("Net Margin", "Net")], "Marj trendi · yıl sonu")
    for i, (mn, lab) in enumerate([("DuPont Net Margin", "Net marj"), ("DuPont Asset Turnover", "× Devir"),
                                   ("DuPont Equity Multiplier", "× Çarpan"), ("ROE (annualized)", "= ROE")]):
        card(p, f"p2_dp{i}", mn, 646 + i * 95, 184, 89, 74, display=lab, size=13)
    p.add("p2_dupont", "tableEx", 646, 266, 372, 150,
          {"Values": [("dim_date.period_label", "Yıl sonu"), ("DuPont Net Margin", "Net marj"),
                      ("DuPont Asset Turnover", "Varlık devri"), ("DuPont Equity Multiplier", "Özk. çarpanı"),
                      ("ROE (annualized)", "ROE")]},
          title="DuPont ayrıştırması · yıl sonu",
          sort=("dim_date.period_label", "Descending"), filters=year_end_filter("p2_dupont_ye"))
    p.no_filter.append("p2_dupont")
    card(p, "p2_issue", "Data Issue Banner", 1028, 184, 240, 112, text=True, size=9, title="Veri uyarısı")
    card(p, "p2_tms", "Growth Banner", 1028, 304, 240, 112, text=True, size=9, title="Karşılaştırılabilirlik")
    p.add("p2_wc", "lineClusteredColumnComboChart", 196, 426, 531, 232,
          {"Category": ["dim_date.period_label"],
           "Y": [("DIO (days)", "Stok günü"), ("DSO (days)", "Alacak günü"), ("DPO (days)", "Borç günü")],
           "Y2": [("Cash Conversion Cycle (days)", "Nakit çevrim süresi")]},
          title="Çalışma sermayesi (gün) · yıl sonu", sort=("dim_date.period_label", "Ascending"),
          objects={"dataPoint": metric_colors(["DIO (days)", "DSO (days)", "DPO (days)",
                                               "Cash Conversion Cycle (days)"])},
          filters=year_end_filter("p2_wc_ye"))
    p.no_filter.append("p2_wc")
    p.add("p2_cash", "lineClusteredColumnComboChart", 737, 426, 531, 232,
          {"Category": ["dim_date.period_label"], "Y": [("OCF to EBITDA", "FNA / FAVÖK")],
           "Y2": [("FCF Margin", "Serbest nakit akışı marjı")]},
          title="Nakit üretimi · yıl sonu (1,0 = FAVÖK'ün tamamı nakde dönüyor)",
          sort=("dim_date.period_label", "Ascending"),
          objects={"dataPoint": metric_colors(["OCF to EBITDA", "FCF Margin"]), "labels": props(show=True, fontSize=8)},
          filters=year_end_filter("p2_cash_ye"))
    p.no_filter.append("p2_cash")
    footer(p)
    pages.append(p)

    # --- Sayfa 3: Likidite ve borçluluk ---
    p = Page("p3_liquidity", "Likidite ve Borçluluk")
    sidebar(p, p.name)
    header(p, "Likidite ve Borçluluk", "Dönem sonu bakiyeler · FAVÖK yıllıklandırılmış · boş oranlar bilerek boş",
           "Blank Ratio Note")
    for i, (mn, t, goal, low) in enumerate([
            ("Current Ratio", "Ort. cari oran", "Current Ratio PY", False),
            ("Quick Ratio", "Ort. asit-test oranı", "Quick Ratio PY", False),
            ("Cash Ratio", "Ort. nakit oranı", "Cash Ratio PY", False),
            ("Net Debt to EBITDA", "Ort. net borç / FAVÖK", "Net Debt to EBITDA PY", True),
            ("Liabilities to Assets", "Ort. yükümlülük / varlık", "Liabilities to Assets PY", True),
            ("OCF to EBITDA", "Ort. FNA / FAVÖK", "OCF to EBITDA PY", False)]):
        kpi(p, f"p3_kpi{i}", mn, KX[i], 70, 172, 104, t, goal, low)
    line_chart(p, "p3_current_ratio", 196, 184, 531, 232, [("Current Ratio", "Cari oran")],
               "Cari oran · yıl sonu", series="dim_company.short_name")
    line_chart(p, "p3_net_debt", 737, 184, 531, 232, [("Net Debt to EBITDA", "Net borç / FAVÖK")],
               "Net borç / FAVÖK · yıl sonu (Şok 2024: FAVÖK ≈ 0, hesaplanmadı)", series="dim_company.short_name")
    p.add("p3_scatter", "scatterChart", 196, 426, 440, 232,
          {"Category": ["dim_company.short_name"], "Series": ["dim_company.short_name"],
           "X": [("Net Debt to EBITDA", "Net borç / FAVÖK")], "Y": [("ROE (annualized)", "ROE (yıllık)")]},
          title="Kaldıraç ve özkaynak getirisi (seçili dönem) · sol üst = iyi",
          objects={"categoryLabels": [{"properties": {"show": lit(True), "fontSize": num(9), "color": solid(INK)}}],
                   "bubbles": props(bubbleSize=8)})
    p.add("p3_table", "tableEx", 646, 426, 622, 232,
          {"Values": ["dim_company.short_name", ("Current Ratio", "Cari oran"), ("Quick Ratio", "Asit-test"),
                      ("Cash Ratio", "Nakit oranı"), ("Net Debt to EBITDA", "Net borç / FAVÖK"),
                      ("Fin Debt to Equity", "Fin. borç / özk."),
                      ("Leverage Rank (1 = lowest)", "Kaldıraç sırası")]},
          title="Likidite ve borçluluk (seçili dönem) · sıra 1 = en düşük kaldıraç")
    footer(p)
    pages.append(p)
    return pages


def build_report(root, theme_src):
    rp = root / f"{NAME}.Report"
    write_json(rp / "definition.pbir", {
        "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    d = rp / "definition"
    theme_name = Path(theme_src).stem if theme_src else "CY26SU10"
    ver = {"visual": V_VISUAL, "page": V_PAGE, "report": V_REPORT}
    report = {
        "$schema": f"{SCHEMA}/item/report/definition/report/{V_REPORT}/schema.json",
        "themeCollection": {
            "baseTheme": {"name": theme_name, "type": "SharedResources", "reportVersionAtImport": ver},
            "customTheme": {"name": f"{THEME_NAME}.json", "type": "RegisteredResources", "reportVersionAtImport": ver}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": theme_name, "path": f"BaseThemes/{theme_name}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": f"{THEME_NAME}.json", "path": f"{THEME_NAME}.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "allowChangeFilterTypes": True,
                     "useEnhancedTooltips": True},
    }
    write_json(d / "report.json", report)
    write_json(rp / "StaticResources" / "RegisteredResources" / f"{THEME_NAME}.json", theme_json())
    write_json(d / "version.json", {"$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
                                    "version": "2.0.0"})
    pages = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        page = {"$schema": f"{SCHEMA}/item/report/definition/page/{V_PAGE}/schema.json",
                "name": p.name, "displayName": p.display, "displayOption": "FitToPage",
                "height": 720, "width": 1280,
                # dönem slicer'ı trend görsellerini filtrelemez (yıl sonu serisi hep görünür)
                "visualInteractions": [{"source": p.period, "target": t, "type": "NoFilter"} for t in p.no_filter]}
        write_json(d / "pages" / p.name / "page.json", page)
        for v in p.visuals:
            write_json(d / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    if theme_src:
        dst = rp / "StaticResources" / "SharedResources" / "BaseThemes" / f"{theme_name}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(theme_src, dst)
    return pages


def main():
    theme = sys.argv[1] if len(sys.argv) > 1 else None
    if not theme:
        found = sorted(glob.glob(THEME_GLOB))
        theme = found[-1] if found else None
    if not theme:
        print("UYARI: Power BI temel tema dosyası bulunamadı; rapor tema olmadan yazılıyor.")
    if OUT.exists():
        shutil.rmtree(OUT)
    build_model(OUT)
    pages = build_report(OUT, theme)
    write_json(OUT / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}})
    write(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"Yazıldı: {OUT / (NAME + '.pbip')}")
    print(f"Tablo: {len(TABLES) + 1}, ölçü: {len(M)}, sayfa: {len(pages)}, "
          f"görsel: {sum(len(p.visuals) for p in pages)}, tema: {Path(theme).name if theme else '-'}")


if __name__ == "__main__":
    main()
