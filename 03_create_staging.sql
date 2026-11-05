/* =====================================================================
   RetailFinance - Aşama 3a: Staging tablosu
   Çalıştırma: SSMS'te tamamını çalıştır. Tekrar çalıştırılırsa tabloyu sıfırlar.
   Ardından: python 03_load_staging.py
   ===================================================================== */
USE RetailFinance;
GO

IF OBJECT_ID(N'stg.raw_financials') IS NOT NULL DROP TABLE stg.raw_financials;
GO

CREATE TABLE stg.raw_financials (
    load_id       BIGINT IDENTITY(1,1) CONSTRAINT PK_stg_raw_financials PRIMARY KEY,
    symbol        VARCHAR(10)   NOT NULL,
    item_code     VARCHAR(30)   NOT NULL,   -- FINANCIAL_ITEM_CODE (1A, 1AA, ...)
    item_name_tr  NVARCHAR(250) NULL,
    item_name_en  NVARCHAR(250) NULL,       -- bazı kalemlerde kaynakta boş
    period_label  VARCHAR(10)   NOT NULL,   -- '2019/3' (dw.dim_date.period_label ile aynı biçim)
    raw_value     FLOAT         NULL,       -- kaynakta nasıl geldiyse (ham); NULL = kaynakta boş. DECIMAL'e dw'de çevrilir
    source_file   VARCHAR(100)  NOT NULL,
    loaded_at     DATETIME2(0)  NOT NULL CONSTRAINT DF_stg_loaded DEFAULT SYSDATETIME(),
    CONSTRAINT UQ_stg_grain UNIQUE (symbol, item_code, period_label)
);
GO

SELECT COUNT(*) AS stg_rows FROM stg.raw_financials;  -- yükleme öncesi: 0
GO

/* --- Yükleme SONRASI kontrol sorguları (loader zaten kendi kontrolünü yapar) ---
SELECT symbol, COUNT(*) AS satir, SUM(CASE WHEN raw_value IS NULL THEN 1 ELSE 0 END) AS bos
FROM stg.raw_financials GROUP BY symbol ORDER BY symbol;   -- beklenen: her biri 4116 satır, 4 boş

SELECT COUNT(*) AS toplam FROM stg.raw_financials;           -- beklenen: 16464
*/
