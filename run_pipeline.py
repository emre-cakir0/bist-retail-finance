"""
RetailFinance - Tüm SQL tarafını sıfırdan çalıştırır (Aşama 1, 3, 4, 5, 6).
Önkoşul: data/raw/*.csv mevcut olmalı (python 02_extract_raw.py ile çekilir; ağ gerektirir).
Kullanım:  python run_pipeline.py
"""
import subprocess
import sys

STEPS = [
    ("Aşama 1  - şema ve seed",            ["run_sql.py", "01_create_schema.sql", "10"]),
    ("Aşama 3a - staging tablosu",         ["run_sql.py", "03_create_staging.sql", "10"]),
    ("Aşama 3b - CSV -> staging",          ["03_load_staging.py"]),
    ("Aşama 4  - standartlaştırma ve fact", ["run_sql.py", "04_standardize.sql", "10"]),
    ("Aşama 5  - analiz katmanı",          ["run_sql.py", "05_analytics.sql", "10"]),
    ("Aşama 6  - veri kalite testleri",    ["run_sql.py", "06_quality_checks.sql", "10"]),
]

for title, args in STEPS:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)
    code = subprocess.call([sys.executable, *args])
    if code != 0:
        print(f"\n[DURDU] '{title}' hata ile bitti (çıkış kodu {code}).")
        sys.exit(code)
print("\nPipeline tamamlandı.")
