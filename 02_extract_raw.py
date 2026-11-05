"""
RetailFinance - Aşama 2: Ham veri çekme
Çalıştırma:  pip install isyatirimhisse pandas
             python 02_extract_raw.py

Çıktı: data/raw/<TICKER>.csv  (4 şirket)
Amaç : Veriyi DEĞİŞTİRMEDEN kaydetmek ve gerçek yapısını (kolonlar, kalem kodları) görmek.
Not  : isyatirimhisse resmi bir kaynak değildir; kişisel kullanım. Doğrulama için KAP.
"""
import inspect
import sys
from pathlib import Path

import pandas as pd
from isyatirimhisse import fetch_financials

TICKERS = ["BIMAS", "MGROS", "SOKM", "CRFSA"]
START_YEAR = 2019
END_YEAR = 2025
FINANCIAL_GROUP = "1"   # '1' = XI_29 (reel sektör, UFRS). Bankalar farklı gruptadır (kapsam dışı).
OUT_DIR = Path("data/raw")


def fetch_one(ticker: str) -> pd.DataFrame:
    return fetch_financials(
        symbols=ticker,
        start_year=START_YEAR,
        end_year=END_YEAR,
        exchange="TRY",
        financial_group=FINANCIAL_GROUP,
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("fetch_financials imzası:", inspect.signature(fetch_financials))
    results, errors = {}, {}

    for t in TICKERS:
        try:
            df = fetch_one(t)
            if df is None or len(df) == 0:
                errors[t] = "boş sonuç döndü"
                continue
            path = OUT_DIR / f"{t}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            results[t] = df
            print(f"[OK]   {t}: boyut={df.shape} -> {path}")
        except Exception as e:  # hatayı yutmadan raporla, diğer şirketlere devam et
            errors[t] = f"{type(e).__name__}: {e}"
            print(f"[HATA] {t}: {errors[t]}")

    print("\n=== ÖZET (Claude'a gönderilecek) ===")
    if "BIMAS" in results:
        b = results["BIMAS"]
        print(f"BIMAS boyut: {b.shape}")
        print("BIMAS kolonlar:", list(b.columns))
        with pd.option_context("display.max_columns", 12, "display.width", 200):
            print(b.head(5))
    else:
        print("BIMAS çekilemedi:", errors.get("BIMAS"))

    for t in TICKERS[1:]:
        if t in results:
            print(f"{t} boyut: {results[t].shape}")
        else:
            print(f"{t} hata: {errors.get(t)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())