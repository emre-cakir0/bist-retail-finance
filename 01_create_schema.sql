/* =====================================================================
   RetailFinance - Aşama 1: SQL Server altyapısı
   Çalıştırma: SSMS'te tamamını çalıştır (F5)  veya  python run_sql.py 01_create_schema.sql
   Tekrar çalıştırılabilir (dw tabloları sıfırlanır; stg şemasına dokunmaz).
   Beklenen sonuç: dim_company = 4 satır, dim_date = 28 satır
   ===================================================================== */

-- 1) Veritabanı --------------------------------------------------------
IF DB_ID(N'RetailFinance') IS NULL
    CREATE DATABASE RetailFinance;
GO

USE RetailFinance;
GO

-- 2) Şemalar -----------------------------------------------------------
IF SCHEMA_ID(N'stg') IS NULL EXEC(N'CREATE SCHEMA stg');
GO
IF SCHEMA_ID(N'dw')  IS NULL EXEC(N'CREATE SCHEMA dw');
GO

-- 3) Tablolar (bağımlılık sırasının tersiyle silinir, sonra oluşturulur) --
--    Not: stg.raw_financials Aşama 3'te (03_create_staging.sql) oluşturulur.
IF OBJECT_ID(N'dw.fact_financials') IS NOT NULL DROP TABLE dw.fact_financials;
IF OBJECT_ID(N'dw.dim_account')     IS NOT NULL DROP TABLE dw.dim_account;
IF OBJECT_ID(N'dw.dim_date')        IS NOT NULL DROP TABLE dw.dim_date;
IF OBJECT_ID(N'dw.dim_company')     IS NOT NULL DROP TABLE dw.dim_company;
GO

CREATE TABLE dw.dim_company (
    company_key      INT IDENTITY(1,1) CONSTRAINT PK_dim_company PRIMARY KEY,
    ticker           VARCHAR(10)   NOT NULL CONSTRAINT UQ_dim_company_ticker UNIQUE,
    company_name     NVARCHAR(150) NOT NULL,
    short_name       NVARCHAR(30)  NOT NULL,
    sector           NVARCHAR(50)  NOT NULL,
    financial_group  VARCHAR(20)   NULL,   -- İş Yatırım financial_group; Aşama 4'te XI_29 olarak doldurulur
    tms29_start_date DATE          NULL    -- Aşama 4'te SPK kararı / şirket açıklamasıyla doldurulur
);
GO

CREATE TABLE dw.dim_date (
    date_key        INT         NOT NULL CONSTRAINT PK_dim_date PRIMARY KEY,  -- YYYYMM (202512)
    period_end_date DATE        NOT NULL,
    fiscal_year     SMALLINT    NOT NULL,
    fiscal_quarter  TINYINT     NOT NULL,
    period_month    TINYINT     NOT NULL,   -- 3, 6, 9, 12 (İş Yatırım dönem değeri)
    period_label    VARCHAR(10) NOT NULL,   -- '2019/3'
    year_quarter    VARCHAR(8)  NOT NULL,   -- '2019-Q1'
    is_tms29_era    BIT         NOT NULL    -- 2023/12 ve sonrası: TMS 29 uygulaması
);
GO

CREATE TABLE dw.dim_account (
    account_key    INT IDENTITY(1,1) CONSTRAINT PK_dim_account PRIMARY KEY,
    account_code   VARCHAR(30)   NOT NULL CONSTRAINT UQ_dim_account_code UNIQUE, -- kaynak kalem kodu
    account_name   NVARCHAR(250) NULL,
    statement_type VARCHAR(10)   NULL,   -- BS / IS / CF / MEMO
    is_cumulative  BIT           NULL,   -- IS ve CF akışları: yılbaşından beri kümülatif
    standard_key   VARCHAR(40)   NULL    -- Revenue, COGS, TotalAssets ... (Aşama 4'te doldurulur)
);
GO

CREATE TABLE dw.fact_financials (
    fact_id     BIGINT IDENTITY(1,1) CONSTRAINT PK_fact_financials PRIMARY KEY,
    company_key INT           NOT NULL CONSTRAINT FK_fact_company REFERENCES dw.dim_company(company_key),
    date_key    INT           NOT NULL CONSTRAINT FK_fact_date    REFERENCES dw.dim_date(date_key),
    account_key INT           NOT NULL CONSTRAINT FK_fact_account REFERENCES dw.dim_account(account_key),
    value       DECIMAL(28,2) NULL,      -- raporlandığı gibi (kümülatif ise kümülatif)
    currency    CHAR(3)       NOT NULL CONSTRAINT DF_fact_currency DEFAULT 'TRY',
    is_tms29    BIT           NOT NULL CONSTRAINT DF_fact_tms29 DEFAULT 0,
    loaded_at   DATETIME2(0)  NOT NULL CONSTRAINT DF_fact_loaded DEFAULT SYSDATETIME(),
    CONSTRAINT UQ_fact_grain UNIQUE (company_key, date_key, account_key)  -- mükerrer kayıt engeli
);
GO

-- 4) Seed: şirketler -----------------------------------------------------
INSERT INTO dw.dim_company (ticker, company_name, short_name, sector) VALUES
 ('BIMAS', N'BİM Birleşik Mağazalar A.Ş.',                         N'BİM',         N'Perakende'),
 ('MGROS', N'Migros Ticaret A.Ş.',                                 N'Migros',      N'Perakende'),
 ('SOKM',  N'Şok Marketler Ticaret A.Ş.',                          N'Şok',         N'Perakende'),
 ('CRFSA', N'CarrefourSA Carrefour Sabancı Ticaret Merkezi A.Ş.',  N'CarrefourSA', N'Perakende');
GO

-- 5) Seed: dönemler (2019/3 - 2025/12, çeyreklik = 28 satır) -------------
;WITH y AS (
    SELECT TOP (7) 2018 + ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS yr FROM sys.all_objects
), q AS (
    SELECT 1 AS qt UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
)
INSERT INTO dw.dim_date (date_key, period_end_date, fiscal_year, fiscal_quarter,
                         period_month, period_label, year_quarter, is_tms29_era)
SELECT yr * 100 + qt * 3,
       EOMONTH(DATEFROMPARTS(yr, qt * 3, 1)),
       yr, qt, qt * 3,
       CONCAT(yr, '/', qt * 3),
       CONCAT(yr, '-Q', qt),
       CASE WHEN yr >= 2024 OR (yr = 2023 AND qt = 4) THEN 1 ELSE 0 END
FROM y CROSS JOIN q;
GO

-- 6) Kontrol -------------------------------------------------------------
SELECT * FROM dw.dim_company;                              -- beklenen: 4 satır
SELECT COUNT(*) AS dim_date_rows FROM dw.dim_date;         -- beklenen: 28
SELECT MIN(date_key) AS ilk_date_key, MAX(date_key) AS son_date_key FROM dw.dim_date;  -- 201903 / 202512
GO
