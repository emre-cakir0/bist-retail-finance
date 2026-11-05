"""
RetailFinance - Aşama 2b: Ham CSV'lerin yapısını inceleme (salt okunur)
Çalıştırma (02_extract_raw.py ile aynı klasörden):  python 02b_inspect_raw.py
Çıktı: terminale ve data/raw/_inspect.txt dosyasına yazılır.
"""
import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
TICKERS = ["BIMAS", "MGROS", "SOKM", "CRFSA"]
PERIOD_RE = re.compile(r"^\d{4}/\d{1,2}$")

lines = []


def out(s=""):
    print(s)
    lines.append(str(s))


def expected_periods():
    return [f"{y}/{m}" for y in range(2019, 2026) for m in (3, 6, 9, 12)]


data = {}
for t in TICKERS:
    p = RAW_DIR / f"{t}.csv"
    if not p.exists():
        out(f"[YOK] {p} bulunamadı")
        continue
    data[t] = pd.read_csv(p, encoding="utf-8-sig")

if not data:
    raise SystemExit("Hiç CSV okunamadı. Doğru klasörde mi çalıştırdın? (data/raw olmalı)")

first = next(iter(data.values()))
cols = list(first.columns)
period_cols = [c for c in cols if PERIOD_RE.match(str(c))]
meta_cols = [c for c in cols if c not in period_cols]
code_col = next((c for c in meta_cols if "CODE" in str(c).upper()), meta_cols[0])
name_cols = [c for c in meta_cols if "NAME" in str(c).upper()]

out("=== 1) KOLON YAPISI ===")
out(f"Tanıtıcı kolonlar : {meta_cols}")
out(f"Kalem kodu kolonu : {code_col}")
out(f"Dönem kolon sayısı: {len(period_cols)}")
out(f"İlk / son dönem   : {period_cols[0] if period_cols else '-'} / {period_cols[-1] if period_cols else '-'}")
missing = [p for p in expected_periods() if p not in period_cols]
extra = [p for p in period_cols if p not in expected_periods()]
out(f"Beklenen 28 dönemden eksik: {missing if missing else 'yok'}")
out(f"Beklenmeyen dönem kolonu  : {extra if extra else 'yok'}")
out(f"Dönem kolonları sıralı mı : {period_cols == expected_periods()}")

out("\n=== 2) ŞİRKET BAZINDA ===")
for t, df in data.items():
    pc = [c for c in df.columns if PERIOD_RE.match(str(c))]
    dup = df[code_col].duplicated().sum()
    nulls = int(df[pc].isna().sum().sum())
    allzero = int((df[pc].fillna(0) == 0).all(axis=1).sum())
    out(f"{t}: boyut={df.shape}, mükerrer kod={dup}, boş hücre={nulls}, tamamı 0/boş satır={allzero}, "
        f"kolonlar aynı mı={list(df.columns) == cols}")

out("\n=== 3) KALEM KODU UYUMU (4 şirket) ===")
sets = {t: set(df[code_col].astype(str)) for t, df in data.items()}
common = set.intersection(*sets.values())
union = set.union(*sets.values())
out(f"Ortak kod sayısı: {len(common)} / toplam farklı kod: {len(union)}")
for t, s in sets.items():
    only = sorted(s - common)
    out(f"{t} sadece kendinde olan: {len(only)} {only[:10]}")

# Aynı kodun şirketler arasında aynı ada sahip olup olmadığı
if name_cols:
    nc = name_cols[0]
    ref = data[next(iter(data))].set_index(code_col)[nc].to_dict()
    diff = 0
    for t, df in data.items():
        m = df.set_index(code_col)[nc].to_dict()
        diff += sum(1 for k in common if m.get(k) != ref.get(k))
    out(f"Ortak kodlarda ad farkı sayısı ({nc}): {diff}")

out("\n=== 4) KOD ÖNEKİ DAĞILIMI (ilk şirket) ===")
pref = first[code_col].astype(str).str[:1].value_counts().sort_index()
out(pref.to_string())

out("\n=== 5) İLK 5 SATIR (ilk şirket, tanıtıcı kolonlar + son 2 dönem) ===")
show = meta_cols + period_cols[-2:]
with pd.option_context("display.max_columns", 20, "display.width", 250, "display.max_colwidth", 45):
    out(first[show].head(5).to_string())

out("\n=== 6) TÜM KALEMLER (ilk şirket: kod | ad | son dönem değeri) ===")
for _, r in first.iterrows():
    nm = " | ".join(str(r[c]) for c in name_cols)
    out(f"{r[code_col]} | {nm} | {r[period_cols[-1]] if period_cols else ''}")

(RAW_DIR / "_inspect.txt").write_text("\n".join(lines), encoding="utf-8")
print(f"\nTamamı şuraya yazıldı: {RAW_DIR / '_inspect.txt'}")