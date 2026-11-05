/* =====================================================================
   RetailFinance - Aşama 4: Standartlaştırma
   - dim_account (147 kalem) + standart anahtar eşleştirmesi (36 anahtar)
   - TMS 29 bayrağı (dim_company.tms29_start_date)
   - dw.usp_load_financials : stg -> dim_account + fact_financials (tekrar çalıştırılabilir)
   - dw.vw_fact_quarterly   : kümülatif (YTD) değerlerden çeyreklik türetme
   - dw.known_data_issues   : kaynak veride tespit edilen sorunların kaydı
   Çalıştırma: SSMS'te F5  veya  python run_sql.py 04_standardize.sql
   ===================================================================== */
USE RetailFinance;
GO

-- 1) Ek kolonlar -------------------------------------------------------
IF COL_LENGTH('dw.dim_company', 'tms29_source') IS NULL
    ALTER TABLE dw.dim_company ADD tms29_source NVARCHAR(500) NULL;
IF COL_LENGTH('dw.dim_account', 'value_kind') IS NULL
    ALTER TABLE dw.dim_account ADD value_kind VARCHAR(10) NULL;   -- AMOUNT / PER_SHARE
GO

-- 2) Şirket bilgileri: finansal grup ve TMS 29 başlangıcı ----------------
--    financial_group: isyatirimhisse belgesi: '1' = XI_29 (v5.0.1)
--    TMS 29: SPK Kurul Kararı 28.12.2023, 81/1820 -> 31.12.2023'te biten hesap dönemi
UPDATE dw.dim_company SET financial_group = 'XI_29', tms29_start_date = '2023-12-31',
    tms29_source = N'SPK Kurul Kararı 28.12.2023 (81/1820). BİM bağımsız denetçi raporu: TMS 29 31.12.2023 itibarıyla uygulanmaya başlandı (BİM 12 Aylık Sonuçlar 2024). Birincil kaynak.'
WHERE ticker = 'BIMAS';
UPDATE dw.dim_company SET financial_group = 'XI_29', tms29_start_date = '2023-12-31',
    tms29_source = N'SPK Kurul Kararı 28.12.2023 (81/1820). Migros 2022-2023 finansallarını enflasyon muhasebesi uygulanmış olarak yayımladı (haber kaynağı). KAP birincil belgesiyle ayrıca teyit edilmeli.'
WHERE ticker = 'MGROS';
UPDATE dw.dim_company SET financial_group = 'XI_29', tms29_start_date = '2023-12-31',
    tms29_source = N'SPK Kurul Kararı 28.12.2023 (81/1820). Şok 4Ç23 sonuçlarını TMS 29 dahil/hariç sundu (Halk Yatırım 4Ç23 raporu). KAP birincil belgesiyle ayrıca teyit edilmeli.'
WHERE ticker = 'SOKM';
UPDATE dw.dim_company SET financial_group = 'XI_29', tms29_start_date = '2023-12-31',
    tms29_source = N'SPK Kurul Kararı 28.12.2023 (81/1820). CarrefourSA ara dönem raporu (30.06.2024): TMS 29, 31.12.2023 tarihli yıllık rapordan başlayarak uygulanmıştır. Birincil kaynak.'
WHERE ticker = 'CRFSA';
GO

-- 3) Standart kalem eşleştirme tablosu ----------------------------------
IF OBJECT_ID('dw.map_standard_account') IS NOT NULL DROP TABLE dw.map_standard_account;
GO
CREATE TABLE dw.map_standard_account (
    standard_key    VARCHAR(40)  NOT NULL CONSTRAINT PK_map_standard PRIMARY KEY,
    account_code    VARCHAR(30)  NOT NULL CONSTRAINT UQ_map_standard_code UNIQUE,
    statement_group VARCHAR(10)  NOT NULL,
    sign_note       NVARCHAR(200) NULL
);
GO
INSERT INTO dw.map_standard_account (standard_key, account_code, statement_group, sign_note) VALUES
 ('CurrentAssets',        '1A',      'BS', NULL),
 ('Cash',                 '1AA',     'BS', N'Nakit ve nakit benzerleri'),
 ('STFinInvestments',     '1AB',     'BS', N'Kısa vadeli finansal yatırımlar'),
 ('TradeReceivables',     '1AC',     'BS', N'Kısa vadeli ticari alacaklar'),
 ('Inventories',          '1AF',     'BS', NULL),
 ('NonCurrentAssets',     '1AK',     'BS', NULL),
 ('TotalAssets',          '1BL',     'BS', NULL),
 ('CurrentLiabilities',   '2A',      'BS', NULL),
 ('STFinDebt',            '2AA',     'BS', N'Kısa vadeli finansal borçlar (kiralama yükümlülükleri dahil olabilir)'),
 ('TradePayables',        '2AAGAA',  'BS', N'Kısa vadeli ticari borçlar'),
 ('NonCurrentLiabilities','2B',      'BS', NULL),
 ('LTFinDebt',            '2BA',     'BS', N'Uzun vadeli finansal borçlar (kiralama yükümlülükleri dahil olabilir)'),
 ('TotalEquity',          '2N',      'BS', N'Azınlık payları dahil'),
 ('ParentEquity',         '2O',      'BS', NULL),
 ('MinorityEquity',       '2ODA',    'BS', NULL),
 ('TotalLiabEquity',      '2ODB',    'BS', N'Toplam kaynaklar; bilanço dengesi testinde kullanılır'),
 ('Revenue',              '3C',      'IS', N'Yılbaşından beri kümülatif'),
 ('COGS',                 '3CA',     'IS', N'Gider, raporlandığı gibi NEGATİF'),
 ('GrossProfit',          '3D',      'IS', NULL),
 ('SellingExpenses',      '3DA',     'IS', N'Gider, NEGATİF'),
 ('AdminExpenses',        '3DB',     'IS', N'Gider, NEGATİF'),
 ('OperatingProfit',      '3DF',     'IS', N'Faaliyet karı; diğer faaliyet gelir/giderleri DAHİL (TMS 29 döneminde kur/parasal etkilerle bozulabilir)'),
 ('CoreOperatingProfit',  '3H',      'IS', N'Net faaliyet kârı = brüt kâr - pazarlama - genel yönetim (- Ar-Ge); diğer faaliyet gelir/giderleri HARİÇ. FAVÖK = 3H + amortisman'),
 ('FinanceExpense',       '3HC',     'IS', N'Finansman gelir/gideri, NET ve işaretli: NEGATİF = net finansman gideri, pozitif = net gelir (TMS 29 parasal kazanç içerebilir). Vergi öncesi kâr = 3HACA + 3HB + 3HC'),
 ('ProfitBeforeTax',      '3I',      'IS', N'Sürdürülen faaliyetler vergi öncesi kâr'),
 ('TaxExpense',           '3IA',     'IS', N'NEGATİF = vergi gideri, pozitif = vergi geliri'),
 ('NetIncome',            '3L',      'IS', N'Dönem kârı (azınlık dahil)'),
 ('NetIncomeParent',      '3Z',      'IS', N'Ana ortaklık payı'),
 ('DepreciationAmort',    '4CAB',    'CF', N'Nakit akış tablosundaki amortisman ve itfa payları (FAVÖK için kullanılır)'),
 ('Depreciation_Memo',    '4B',      'MEMO', N'Ek bilgi kalemi; 4CAB ile küçük farklar olabilir'),
 ('OperatingCashFlow',    '4C',      'CF', NULL),
 ('CapEx',                '4CAI',    'CF', N'Sabit sermaye yatırımları; NEGATİF = nakit çıkışı'),
 ('InvestingCashFlow',    '4CAK',    'CF', NULL),
 ('FinancingCashFlow',    '4CBE',    'CF', NULL),
 ('DividendsPaid',        '4CBB',    'CF', N'NEGATİF = ödenen temettü'),
 ('CashEndOfPeriod',      '4CBL',    'CF', N'Nakit akışı dönem sonu nakit; bilanço nakdiyle birebir eşit olmayabilir');
GO

-- 4) Bilinen veri sorunları kaydı ----------------------------------------
IF OBJECT_ID('dw.known_data_issues') IS NOT NULL DROP TABLE dw.known_data_issues;
GO
CREATE TABLE dw.known_data_issues (
    issue_id     INT IDENTITY(1,1) CONSTRAINT PK_known_issues PRIMARY KEY,
    ticker       VARCHAR(10)   NULL,            -- NULL = tüm şirketler
    period_label VARCHAR(10)   NULL,            -- NULL = tüm dönemler
    scope        VARCHAR(30)   NOT NULL,        -- QUARTERLY_DERIVATION / ALL_COMPARISONS
    severity     VARCHAR(10)   NOT NULL,        -- HIGH / MEDIUM / INFO
    status       VARCHAR(12)   NOT NULL,        -- CONFIRMED / SUSPECTED / INFO
    description  NVARCHAR(1000) NOT NULL,
    evidence     NVARCHAR(1000) NULL
);
GO

INSERT INTO dw.known_data_issues (ticker, period_label, scope, severity, status, description, evidence)
VALUES
 (NULL, NULL, 'ALL_COMPARISONS', 'HIGH', 'INFO',
  N'TMS 29 döneminde (2023/12 ve sonrası) her dönem kolonu kendi dönem sonu satın alma gücüyle ifade edilir. Kolonlar arası işlemler (çeyreklik türetme, YoY, TTM) nominaldir ve satın alma gücü cinsinden karşılaştırılabilir değildir. YTD farkıyla türetilen çeyrekler sonraki çeyrek akışlarını abartır. Aynı kolon içindeki oranlar (marj, cari oran, kaldıraç) bu sorundan etkilenmez.',
  N'BİM 3Ç24: veri setinden türetilen 190,3 mlr TL, resmî çeyreklik hasılat 167,9 mlr TL (VKY Analiz 3Ç25 raporu).');

INSERT INTO dw.known_data_issues (ticker, period_label, scope, severity, status, description, evidence)
SELECT t.ticker, '2022/12', 'QUARTERLY_DERIVATION', 'HIGH', 'CONFIRMED',
  N'2022/12 yıllık kolonu TMS 29 ile yeniden ifade edilmiş karşılaştırma değerlerini taşıyor (2023/3-2023/9 ise orijinal nominal). Toplam varlıklar 2022/9''a göre ~2,6 kat, YTD farkıyla türetilen Q4 2022 geliri ~4 kat çıkıyor. Q4 2022 türetilmiş çeyrekleri ve 2022/12''yi içeren QoQ/YoY büyümeler kullanılmamalı.',
  N'4 şirkette de aynı sıçrama. BİM: toplam varlık 2022/9 = 48,3 mlr TL, 2022/12 = 126,1 mlr TL, 2023/3 = 76,0 mlr TL.'
FROM (VALUES ('BIMAS'),('MGROS'),('SOKM'),('CRFSA')) t(ticker);

INSERT INTO dw.known_data_issues (ticker, period_label, scope, severity, status, description, evidence)
SELECT t.ticker, p.period_label, 'QUARTERLY_DERIVATION', 'HIGH', 'CONFIRMED',
  N'2025/12 yıllık kolonu 2025/9''a göre daha yüksek bir fiyat bazında görünüyor; türetilen Q3 2025 geliri Q2''nin ~yarısı, Q4 2025 ise ~3 katı. Q3/Q4 2025 türetilmiş çeyrekleri güvenilmez. 2025/9 kolonunun kendisi resmî rakamla tutuyor.',
  N'BİM resmî 9A25 hasılat 512.767 mn TL = veri seti 2025/9 (tutuyor). BİM resmî FY2025 hasılat ~721 mlr TL, veri seti 2025/12 = 849,1 mlr TL (x1,18). Migros resmî 2025 hasılat ~413 mlr TL, veri seti 486,1 mlr TL (x1,18). Kaynaklar: VKY Analiz 3Ç25, CNBC-e BİM 4Ç25, Forbes Türkiye Migros 2025.'
FROM (VALUES ('BIMAS'),('MGROS'),('SOKM')) t(ticker)
CROSS JOIN (VALUES ('2025/9'),('2025/12')) p(period_label);

INSERT INTO dw.known_data_issues (ticker, period_label, scope, severity, status, description, evidence)
VALUES
 ('BIMAS', '2025/6', 'ALL_COMPARISONS', 'MEDIUM', 'SUSPECTED',
  N'BİM 2025/6 YTD hasılatı (409,3 mlr TL) resmî çeyreklik rakamlardan türetilen değerle uyuşmuyor; 2025/3 ve 2025/6 kolonları da yeniden ifade edilmiş (yüksek baz) olabilir.',
  N'Resmî 9A25 (512,8) - 3Ç25 (179,7) = ~333 mlr TL (Eylül 2025 TL) beklenirken veri seti 2025/6 = 409,3 mlr TL.');
GO

-- 5) Yükleme prosedürü ---------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_load_financials
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRAN;

    -- dim_account: staging'deki tüm kalemler (ad: Türkçe; İngilizce ad bazı kalemlerde boş)
    MERGE dw.dim_account AS t
    USING (SELECT item_code, MIN(item_name_tr) AS name_tr
           FROM stg.raw_financials GROUP BY item_code) AS s
        ON t.account_code = s.item_code
    WHEN MATCHED THEN UPDATE SET account_name = s.name_tr
    WHEN NOT MATCHED THEN INSERT (account_code, account_name) VALUES (s.item_code, s.name_tr);

    UPDATE a SET
        statement_type = CASE WHEN a.account_code LIKE '[12]%' THEN 'BS'
                              WHEN a.account_code LIKE '3%'    THEN 'IS'
                              WHEN a.account_code LIKE '4B%'   THEN 'MEMO'
                              WHEN a.account_code LIKE '4C%'   THEN 'CF' END,
        is_cumulative  = CASE WHEN a.account_code LIKE '[12]%'          THEN 0
                              WHEN a.account_code LIKE '3%'             THEN 1
                              WHEN a.account_code LIKE '4BE%'           THEN 0   -- net YP pozisyonu: dönem sonu stok
                              WHEN a.account_code IN ('4CBK','4CBL')    THEN 0   -- dönem başı/sonu nakit: stok
                              ELSE 1 END,
        value_kind     = CASE WHEN a.account_code IN ('3ZD','3ZE','3ZF','3ZG') THEN 'PER_SHARE' ELSE 'AMOUNT' END,
        standard_key   = m.standard_key
    FROM dw.dim_account a
    LEFT JOIN dw.map_standard_account m ON m.account_code = a.account_code;

    -- fact_financials: kaynakta boş olmayan tüm değerler, raporlandığı gibi
    TRUNCATE TABLE dw.fact_financials;
    INSERT INTO dw.fact_financials (company_key, date_key, account_key, value, currency, is_tms29)
    SELECT c.company_key, d.date_key, a.account_key,
           CAST(s.raw_value AS DECIMAL(28,2)), 'TRY',
           CASE WHEN c.tms29_start_date IS NOT NULL AND d.period_end_date >= c.tms29_start_date THEN 1 ELSE 0 END
    FROM stg.raw_financials s
    JOIN dw.dim_company c ON c.ticker       = s.symbol
    JOIN dw.dim_date    d ON d.period_label = s.period_label
    JOIN dw.dim_account a ON a.account_code = s.item_code
    WHERE s.raw_value IS NOT NULL;

    COMMIT;

    SELECT (SELECT COUNT(*) FROM dw.dim_account)                               AS dim_account_rows,
           (SELECT COUNT(*) FROM dw.dim_account WHERE standard_key IS NOT NULL) AS mapped_accounts,
           (SELECT COUNT(*) FROM dw.fact_financials)                            AS fact_rows;
END;
GO

-- 6) Çeyreklik görünüm ---------------------------------------------------
--    Akış kalemleri (is_cumulative=1): Q1 = YTD, Qn = YTD(n) - YTD(n-1).
--    Stok kalemleri (bilanço vb.): dönem sonu değeri.
--    DİKKAT: TMS 29 döneminde fark nominaldir, bkz. dw.known_data_issues.
CREATE OR ALTER VIEW dw.vw_fact_quarterly
AS
SELECT
    f.company_key, c.ticker, c.short_name,
    d.date_key, d.period_label, d.fiscal_year, d.fiscal_quarter, d.year_quarter,
    a.account_key, a.account_code, a.account_name, a.standard_key, a.statement_type, a.is_cumulative,
    f.value AS value_reported,
    CASE WHEN a.is_cumulative = 0     THEN f.value
         WHEN d.fiscal_quarter = 1    THEN f.value
         ELSE f.value - p.value END   AS value_quarterly,
    f.is_tms29
FROM dw.fact_financials f
JOIN dw.dim_company c ON c.company_key = f.company_key
JOIN dw.dim_date    d ON d.date_key    = f.date_key
JOIN dw.dim_account a ON a.account_key = f.account_key
LEFT JOIN dw.fact_financials p
       ON p.company_key = f.company_key
      AND p.account_key = f.account_key
      AND p.date_key    = f.date_key - 3
      AND d.fiscal_quarter > 1;
GO

-- 7) Yükle ve doğrula ----------------------------------------------------
EXEC dw.usp_load_financials;
GO

SELECT c.ticker,
       COUNT(*)                                       AS fact_rows,
       COUNT(DISTINCT f.date_key)                     AS periods,
       SUM(CASE WHEN f.is_tms29 = 1 THEN 1 ELSE 0 END) AS tms29_rows,
       COUNT(DISTINCT CASE WHEN f.is_tms29 = 1 THEN f.date_key END) AS tms29_periods
FROM dw.fact_financials f JOIN dw.dim_company c ON c.company_key = f.company_key
GROUP BY c.ticker ORDER BY c.ticker;
GO

SELECT statement_type, COUNT(*) AS accounts,
       SUM(CASE WHEN standard_key IS NOT NULL THEN 1 ELSE 0 END) AS mapped,
       SUM(CASE WHEN is_cumulative = 1 THEN 1 ELSE 0 END)        AS cumulative
FROM dw.dim_account GROUP BY statement_type ORDER BY statement_type;
GO
