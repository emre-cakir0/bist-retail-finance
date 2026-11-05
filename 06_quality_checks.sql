/* =====================================================================
   RetailFinance - Aşama 6: Veri kalite kontrolleri
   Sonuçlar dw.dq_results tablosunda (test, şirket, dönem, sonuç) saklanır.
   Sonuç değerleri:
     PASS      test geçti
     EXPLAINED test geçmedi ama dw.known_data_issues içinde belgelenmiş istisna
     FAIL      açıklanmamış hata
   Çalıştırma: python run_sql.py 06_quality_checks.sql   (veya SSMS: EXEC dw.usp_run_quality_checks)
   ===================================================================== */
USE RetailFinance;
GO

IF OBJECT_ID('dw.dq_results') IS NOT NULL DROP TABLE dw.dq_results;
GO
CREATE TABLE dw.dq_results (
    result_id    INT IDENTITY(1,1) CONSTRAINT PK_dq_results PRIMARY KEY,
    run_at       DATETIME2(0)  NOT NULL CONSTRAINT DF_dq_run_at DEFAULT SYSDATETIME(),
    test_name    VARCHAR(40)   NOT NULL,
    ticker       VARCHAR(10)   NULL,
    period_label VARCHAR(10)   NULL,
    result       VARCHAR(10)   NOT NULL CONSTRAINT CK_dq_result CHECK (result IN ('PASS','FAIL','EXPLAINED')),
    detail       NVARCHAR(1000) NULL
);
GO

CREATE OR ALTER VIEW dw.vw_dq_summary
AS
SELECT test_name,
       COUNT(*)                                                 AS total_checks,
       SUM(CASE WHEN result = 'PASS'      THEN 1 ELSE 0 END)    AS pass_count,
       SUM(CASE WHEN result = 'EXPLAINED' THEN 1 ELSE 0 END)    AS explained_count,
       SUM(CASE WHEN result = 'FAIL'      THEN 1 ELSE 0 END)    AS fail_count
FROM dw.dq_results
GROUP BY test_name;
GO

CREATE OR ALTER PROCEDURE dw.usp_run_quality_checks
AS
BEGIN
    SET NOCOUNT ON;
    TRUNCATE TABLE dw.dq_results;

    -- 1) Bilanço dengesi: toplam varlıklar = toplam kaynaklar (pasif); ayrıca 1A+1AK ve 2A+2B+2N kırılımları
    --    Tolerans 1.000 TL: kaynak değerler binlik yuvarlanmış.
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'BS_BALANCE', ticker, period_label,
           CASE WHEN ABS(total_assets - total_liab_equity) <= 1000
                 AND ABS(total_assets - (current_liabilities + non_current_liabilities + total_equity)) <= 1000
                 AND ABS(total_assets - (current_assets + non_current_assets)) <= 1000 THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(N'Varlık - kaynak farkı: ', CAST(ABS(total_assets - total_liab_equity) AS BIGINT), N' TL (tolerans 1.000 TL)')
    FROM dw.vw_std_ytd;

    -- 2) Çeyrek toplamı: 4 çeyreğin toplamı yıllık değere eşit ve eksik çeyrek yok
    --    (türetme bütünlüğü testi; çeyrekler YTD farkından üretildiği için toplam yapısal olarak eşittir,
    --     test eksik dönem/kalem ve hatalı türetmeyi yakalar. Makullük için sonraki teste bakın.)
    ;WITH k AS (
        SELECT ticker, fiscal_year, standard_key,
               COUNT(value_quarterly) AS n_q,
               SUM(value_quarterly)   AS sum_q,
               MAX(CASE WHEN fiscal_quarter = 4 THEN value_reported END) AS fy_value
        FROM dw.vw_fact_quarterly
        WHERE standard_key IN ('Revenue','COGS','GrossProfit','CoreOperatingProfit','NetIncome','OperatingCashFlow')
        GROUP BY ticker, fiscal_year, standard_key
    )
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'QUARTER_SUM', ticker, CONCAT(fiscal_year, '/12'),
           CASE WHEN SUM(CASE WHEN n_q = 4 AND ABS(sum_q - fy_value) < 0.01 THEN 1 ELSE 0 END) = COUNT(*) THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(SUM(CASE WHEN n_q = 4 AND ABS(sum_q - fy_value) < 0.01 THEN 1 ELSE 0 END), '/', COUNT(*),
                  N' gelir tablosu/nakit akışı kaleminde 4 çeyrek toplamı yıllık değere eşit')
    FROM k
    GROUP BY ticker, fiscal_year;

    -- 3) Çeyrek makullüğü: türetilmiş çeyreklik gelir > 0 ve önceki çeyreğe oranı 0,5 - 2,0 arasında
    --    İstisna dw.known_data_issues'ta belgeliyse EXPLAINED, değilse FAIL.
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'QUARTER_PLAUSIBILITY', ticker, period_label,
           CASE WHEN revenue_q > 0 AND (revenue_qoq_nominal IS NULL OR revenue_qoq_nominal BETWEEN -0.5 AND 1.0) THEN 'PASS'
                WHEN known_issue_flag = 1 THEN 'EXPLAINED'
                ELSE 'FAIL' END,
           CONCAT(N'Çeyreklik gelir / önceki çeyrek = ',
                  ISNULL(CAST(CAST(ROUND(revenue_qoq_nominal + 1, 2) AS DECIMAL(10,2)) AS VARCHAR(20)), N'-'),
                  N' (beklenen aralık 0,5 - 2,0)',
                  CASE WHEN known_issue_flag = 1 THEN N'; bkz. dw.known_data_issues' ELSE N'' END)
    FROM dw.vw_quarterly_std;

    -- 4) Eksik dönem: her şirket için beklenen tüm dönemler (dim_date) mevcut
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'MISSING_PERIODS', c.ticker, NULL,
           CASE WHEN x.ta = e.n AND x.rev = e.n THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(N'Toplam varlık ', x.ta, '/', e.n, N' dönem; gelir ', x.rev, '/', e.n, N' dönem')
    FROM dw.dim_company c
    CROSS APPLY (SELECT COUNT(*) AS n FROM dw.dim_date) e
    CROSS APPLY (SELECT COUNT(DISTINCT CASE WHEN a.standard_key = 'TotalAssets' THEN f.date_key END) AS ta,
                        COUNT(DISTINCT CASE WHEN a.standard_key = 'Revenue'     THEN f.date_key END) AS rev
                 FROM dw.fact_financials f
                 JOIN dw.dim_account a ON a.account_key = f.account_key
                 WHERE f.company_key = c.company_key) x;

    -- 5) Mükerrer kayıt: aynı şirket + dönem + kalem için tek satır (staging ve fact)
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'DUPLICATES_STG', NULL, NULL,
           CASE WHEN d.n = 0 THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(d.n, N' mükerrer (şirket, dönem, kalem) grubu')
    FROM (SELECT COUNT(*) AS n FROM (SELECT 1 AS x FROM stg.raw_financials
                                     GROUP BY symbol, item_code, period_label HAVING COUNT(*) > 1) q) d;

    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'DUPLICATES_FACT', c.ticker, NULL,
           CASE WHEN d.n = 0 THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(d.n, N' mükerrer (dönem, kalem) grubu')
    FROM dw.dim_company c
    CROSS APPLY (SELECT COUNT(*) AS n FROM (SELECT 1 AS x FROM dw.fact_financials f
                                            WHERE f.company_key = c.company_key
                                            GROUP BY f.date_key, f.account_key HAVING COUNT(*) > 1) q) d;

    -- 6) Eşleştirme kapsamı: standart kalem listesindeki her anahtar 4 şirkette de tüm dönemlerde dolu
    ;WITH cov AS (
        SELECT c.ticker, m.standard_key, COUNT(DISTINCT f.date_key) AS n
        FROM dw.dim_company c
        CROSS JOIN dw.map_standard_account m
        LEFT JOIN dw.dim_account a ON a.standard_key = m.standard_key
        LEFT JOIN dw.fact_financials f ON f.account_key = a.account_key AND f.company_key = c.company_key
        GROUP BY c.ticker, m.standard_key
    ), agg AS (
        SELECT cov.ticker,
               COUNT(*) AS total_keys,
               SUM(CASE WHEN cov.n = e.np THEN 1 ELSE 0 END) AS ok_keys,
               STRING_AGG(CASE WHEN cov.n < e.np THEN cov.standard_key END, ',') AS missing_keys
        FROM cov
        CROSS JOIN (SELECT COUNT(*) AS np FROM dw.dim_date) e
        GROUP BY cov.ticker
    )
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'MAPPING_COVERAGE', ticker, NULL,
           CASE WHEN ok_keys = total_keys THEN 'PASS' ELSE 'FAIL' END,
           CONCAT(ok_keys, '/', total_keys, N' standart anahtar tüm dönemlerde dolu',
                  ISNULL(N'; eksik: ' + missing_keys, N''))
    FROM agg;

    -- 7) TMS 29 bayrağı: başlangıç tarihi ve kaynak dolu; bayraklı dönem sayısı beklenenle eşit
    --    Kaynak ikincil (KAP birincil belgesi bekleyen) ise EXPLAINED.
    ;WITH t AS (
        SELECT c.ticker, c.tms29_start_date, c.tms29_source,
               (SELECT COUNT(*) FROM dw.dim_date d WHERE d.period_end_date >= c.tms29_start_date) AS expected,
               COUNT(DISTINCT CASE WHEN f.is_tms29 = 1 THEN f.date_key END) AS flagged,
               COUNT(DISTINCT CASE WHEN f.is_tms29 = 1 AND d2.period_end_date < c.tms29_start_date THEN f.date_key END) AS early_flag
        FROM dw.dim_company c
        JOIN dw.fact_financials f ON f.company_key = c.company_key
        JOIN dw.dim_date d2 ON d2.date_key = f.date_key
        GROUP BY c.company_key, c.ticker, c.tms29_start_date, c.tms29_source
    )
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'TMS29_FLAG', ticker, NULL,
           CASE WHEN tms29_start_date IS NULL OR tms29_source IS NULL THEN 'FAIL'
                WHEN flagged <> expected OR early_flag > 0 THEN 'FAIL'
                WHEN tms29_source LIKE N'%ayrıca teyit%' THEN 'EXPLAINED'
                ELSE 'PASS' END,
           CONCAT(N'Başlangıç ', CONVERT(VARCHAR(10), tms29_start_date, 23),
                  N'; bayraklı dönem ', flagged, '/', expected, N'. ', tms29_source)
    FROM t;

    -- 8) Ek kimlikler: brüt kâr = gelir + SMM; toplam özkaynak = ana ortaklık + azınlık
    INSERT INTO dw.dq_results (test_name, ticker, period_label, result, detail)
    SELECT 'IDENTITIES', ticker, period_label,
           CASE WHEN ABS(gross_profit - (revenue + cogs)) <= 1000
                 AND ABS(total_equity - (parent_equity + minority_equity)) <= 1000 THEN 'PASS' ELSE 'FAIL' END,
           N'Brüt kâr = gelir + SMM ve özkaynak = ana ortaklık + azınlık (tolerans 1.000 TL)'
    FROM dw.vw_std_ytd;

    SELECT * FROM dw.vw_dq_summary ORDER BY test_name;
END;
GO

EXEC dw.usp_run_quality_checks;
GO

-- Geçmeyen (PASS olmayan) satırlar
SELECT test_name, ticker, period_label, result, LEFT(detail, 140) AS detail
FROM dw.dq_results WHERE result <> 'PASS'
ORDER BY result, test_name, ticker, period_label;
GO
SELECT result, COUNT(*) AS n FROM dw.dq_results GROUP BY result ORDER BY result;
GO
