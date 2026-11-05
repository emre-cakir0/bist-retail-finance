"""
RetailFinance - Aşama 3b: CSV -> stg.raw_financials yükleme
Önce SSMS'te 03_create_staging.sql çalıştırılmış olmalı.
Kurulum : pip install pyodbc pandas
Çalıştırma: python 03_load_staging.py   (02_extract_raw.py ile aynı klasörden)

Her çalıştırmada tabloyu TRUNCATE edip baştan yükler (tekrar çalıştırılabilir).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyodbc

SERVER = r"localhost\SQLEXPRESS"
DATABASE = "RetailFinance"
RAW_DIR = Path("data/raw")
TICKERS = ["BIMAS", "MGROS", "SOKM", "CRFSA"]
META = ["FINANCIAL_ITEM_CODE", "FINANCIAL_ITEM_NAME_TR", "FINANCIAL_ITEM_NAME_EN", "SYMBOL"]
CHUNK = 5000


def pick_driver() -> str:
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    modern = sorted((d for d in drivers if d.startswith("ODBC Driver")), reverse=True)
    if modern:
        return modern[0]
    if drivers:
        return drivers[-1]
    raise SystemExit("SQL Server ODBC sürücüsü bulunamadı. 'ODBC Driver 18 for SQL Server' kurulmalı.")


def clean(x):
    # pandas NaN/NA -> SQL NULL (aksi halde pyodbc metin kolonuna sayi gibi gonderir)
    return None if pd.isna(x) else str(x)


def to_long(ticker: str) -> pd.DataFrame:
    path = RAW_DIR / f"{ticker}.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    periods = [c for c in df.columns if c not in META]
    long = df.melt(id_vars=META, value_vars=periods, var_name="period_label", value_name="raw_value")
    long["raw_value"] = pd.to_numeric(long["raw_value"])  # sayı olmayan değer varsa hata verir
    long["source_file"] = path.name
    return long, len(df), len(periods)


def main() -> int:
    frames, expected = [], {}
    for t in TICKERS:
        long, n_rows, n_periods = to_long(t)
        frames.append(long)
        expected[t] = {"rows": n_rows * n_periods, "nulls": int(long["raw_value"].isna().sum())}
    all_long = pd.concat(frames, ignore_index=True)

    vals = all_long["raw_value"].dropna()
    print(f"Ön kontrol: {len(all_long)} satır, min={vals.min():,.0f}, max={vals.max():,.0f}, "
          f"sonsuz/NaN dışı geçersiz={int((~np.isfinite(vals)).sum())}")
    if (~np.isfinite(vals)).any():
        raise SystemExit("Kaynakta sonsuz (inf) değer var; bu satırlar incelenmeli.")

    conn_str = (f"DRIVER={{{pick_driver()}}};SERVER={SERVER};DATABASE={DATABASE};"
                "Trusted_Connection=yes;TrustServerCertificate=yes;")
    print("Bağlanılıyor:", conn_str.split(";")[0], "|", SERVER, "|", DATABASE)
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    cur.fast_executemany = True

    try:
        cur.execute("TRUNCATE TABLE stg.raw_financials")
    except pyodbc.Error as e:
        raise SystemExit(f"stg.raw_financials yok gibi görünüyor. Önce 03_create_staging.sql çalıştır.\n{e}")

    sql = ("INSERT INTO stg.raw_financials "
           "(symbol, item_code, item_name_tr, item_name_en, period_label, raw_value, source_file) "
           "VALUES (?,?,?,?,?,?,?)")
    rows = [
        (r.SYMBOL, r.FINANCIAL_ITEM_CODE, clean(r.FINANCIAL_ITEM_NAME_TR), clean(r.FINANCIAL_ITEM_NAME_EN),
         r.period_label, None if pd.isna(r.raw_value) else float(r.raw_value), r.source_file)
        for r in all_long.itertuples(index=False)
    ]
    for i in range(0, len(rows), CHUNK):
        cur.executemany(sql, rows[i:i + CHUNK])
    conn.commit()

    # --- Doğrulama: stg satır sayıları CSV ile tutuyor mu? ---
    cur.execute("SELECT symbol, COUNT(*), SUM(CASE WHEN raw_value IS NULL THEN 1 ELSE 0 END) "
                "FROM stg.raw_financials GROUP BY symbol")
    got = {s: (n, z) for s, n, z in cur.fetchall()}
    print("\n=== DOĞRULAMA (CSV vs stg) ===")
    ok = True
    for t in TICKERS:
        exp = (expected[t]["rows"], expected[t]["nulls"])
        g = got.get(t, (0, 0))
        status = "OK" if g == exp else "UYUŞMUYOR"
        ok &= g == exp
        print(f"{t}: CSV satır={exp[0]}, stg satır={g[0]} | CSV boş={exp[1]}, stg boş={g[1]}  -> {status}")
    cur.execute("SELECT COUNT(*) FROM stg.raw_financials")
    print(f"Toplam stg satır: {cur.fetchone()[0]}  (beklenen {sum(e['rows'] for e in expected.values())})")

    # --- 4'er boş hücre hangileri? ---
    print("\n=== KAYNAKTA BOŞ OLAN HÜCRELER ===")
    nulls = all_long[all_long["raw_value"].isna()][["SYMBOL", "FINANCIAL_ITEM_CODE", "FINANCIAL_ITEM_NAME_TR", "period_label"]]
    with pd.option_context("display.width", 200, "display.max_colwidth", 50):
        print(nulls.to_string(index=False))

    conn.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())