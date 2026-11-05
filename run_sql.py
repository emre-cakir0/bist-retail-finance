"""
RetailFinance yardımcı araç: bir .sql dosyasını GO ayracına göre parçalayıp çalıştırır.
Kullanım:  python run_sql.py 04_standardize.sql [maksimum_satir]
SSMS'te F5 ile çalıştırmanın komut satırı karşılığıdır; sonuç kümelerini ekrana basar.
"""
import re
import sys
from pathlib import Path

import pyodbc

SERVER = r"localhost\SQLEXPRESS"
DATABASE = "RetailFinance"


def pick_driver() -> str:
    drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
    modern = sorted((d for d in drivers if d.startswith("ODBC Driver")), reverse=True)
    if modern:
        return modern[0]
    if drivers:
        return drivers[-1]
    raise SystemExit("SQL Server ODBC sürücüsü bulunamadı.")


def fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, float):
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return str(v)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("Kullanım: python run_sql.py <dosya.sql> [maksimum_satir]")
    path = Path(sys.argv[1])
    max_rows = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    text = path.read_text(encoding="utf-8-sig")
    batches = [b for b in re.split(r"(?im)^\s*GO\s*$", text) if b.strip()]

    conn = pyodbc.connect(
        f"DRIVER={{{pick_driver()}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;",
        autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("SET NOCOUNT ON")

    for i, batch in enumerate(batches, 1):
        try:
            cur.execute(batch)
            while True:
                if cur.description:
                    cols = [d[0] for d in cur.description]
                    rows = cur.fetchmany(max_rows + 1)
                    print("\n" + " | ".join(cols))
                    for r in rows[:max_rows]:
                        print(" | ".join(fmt(v) for v in r))
                    if len(rows) > max_rows:
                        print(f"... (ilk {max_rows} satır gösterildi)")
                if not cur.nextset():
                    break
        except pyodbc.Error as e:
            head = " ".join(batch.strip().split())[:160]
            print(f"\n[HATA] batch {i}: {e}\n  -> {head}")
            return 1
    print(f"\nTamam: {path.name} ({len(batches)} batch çalıştı)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
