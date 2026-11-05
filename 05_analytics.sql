/* =====================================================================
   RetailFinance - Aşama 5: Analiz katmanı (View ve Stored Procedure)

   TASARIM İLKESİ (bkz. dw.known_data_issues):
   Oranlar AYNI dönem kolonunun içinde hesaplanır (pay ve payda aynı fiyat bazında).
   Akış kalemleri yıllıklandırılır: YTD x 12 / period_month. Bilanço kalemleri dönem sonu
   değeridir (ortalama bakiye kullanılmaz, çünkü dönemler arası TMS 29 bazı farklıdır).
   Kolonlar arası işlemler (çeyreklik fark, YoY) nominaldir ve bayraklanır.

   Çalıştırma: python run_sql.py 05_analytics.sql
   ===================================================================== */
USE RetailFinance;
GO

-- 1) Standart kalemler, geniş biçim, YTD (raporlandığı gibi) -------------
CREATE OR ALTER VIEW dw.vw_std_ytd
AS
SELECT
    c.company_key, c.ticker, c.short_name,
    d.date_key, d.period_label, d.fiscal_year, d.fiscal_quarter, d.year_quarter, d.period_month,
    MAX(CAST(f.is_tms29 AS INT)) AS is_tms29,
    CAST(MAX(CASE WHEN a.standard_key = 'CurrentAssets'         THEN f.value END) AS FLOAT) AS current_assets,
    CAST(MAX(CASE WHEN a.standard_key = 'Cash'                  THEN f.value END) AS FLOAT) AS cash,
    CAST(MAX(CASE WHEN a.standard_key = 'STFinInvestments'      THEN f.value END) AS FLOAT) AS st_fin_investments,
    CAST(MAX(CASE WHEN a.standard_key = 'TradeReceivables'      THEN f.value END) AS FLOAT) AS trade_receivables,
    CAST(MAX(CASE WHEN a.standard_key = 'Inventories'           THEN f.value END) AS FLOAT) AS inventories,
    CAST(MAX(CASE WHEN a.standard_key = 'NonCurrentAssets'      THEN f.value END) AS FLOAT) AS non_current_assets,
    CAST(MAX(CASE WHEN a.standard_key = 'TotalAssets'           THEN f.value END) AS FLOAT) AS total_assets,
    CAST(MAX(CASE WHEN a.standard_key = 'CurrentLiabilities'    THEN f.value END) AS FLOAT) AS current_liabilities,
    CAST(MAX(CASE WHEN a.standard_key = 'STFinDebt'             THEN f.value END) AS FLOAT) AS st_fin_debt,
    CAST(MAX(CASE WHEN a.standard_key = 'TradePayables'         THEN f.value END) AS FLOAT) AS trade_payables,
    CAST(MAX(CASE WHEN a.standard_key = 'NonCurrentLiabilities' THEN f.value END) AS FLOAT) AS non_current_liabilities,
    CAST(MAX(CASE WHEN a.standard_key = 'LTFinDebt'             THEN f.value END) AS FLOAT) AS lt_fin_debt,
    CAST(MAX(CASE WHEN a.standard_key = 'TotalEquity'           THEN f.value END) AS FLOAT) AS total_equity,
    CAST(MAX(CASE WHEN a.standard_key = 'ParentEquity'          THEN f.value END) AS FLOAT) AS parent_equity,
    CAST(MAX(CASE WHEN a.standard_key = 'MinorityEquity'        THEN f.value END) AS FLOAT) AS minority_equity,
    CAST(MAX(CASE WHEN a.standard_key = 'TotalLiabEquity'       THEN f.value END) AS FLOAT) AS total_liab_equity,
    CAST(MAX(CASE WHEN a.standard_key = 'Revenue'               THEN f.value END) AS FLOAT) AS revenue,
    CAST(MAX(CASE WHEN a.standard_key = 'COGS'                  THEN f.value END) AS FLOAT) AS cogs,
    CAST(MAX(CASE WHEN a.standard_key = 'GrossProfit'           THEN f.value END) AS FLOAT) AS gross_profit,
    CAST(MAX(CASE WHEN a.standard_key = 'SellingExpenses'       THEN f.value END) AS FLOAT) AS selling_expenses,
    CAST(MAX(CASE WHEN a.standard_key = 'AdminExpenses'         THEN f.value END) AS FLOAT) AS admin_expenses,
    CAST(MAX(CASE WHEN a.standard_key = 'OperatingProfit'       THEN f.value END) AS FLOAT) AS operating_profit,
    CAST(MAX(CASE WHEN a.standard_key = 'CoreOperatingProfit'   THEN f.value END) AS FLOAT) AS core_operating_profit,
    CAST(MAX(CASE WHEN a.standard_key = 'FinanceExpense'        THEN f.value END) AS FLOAT) AS finance_expense,
    CAST(MAX(CASE WHEN a.standard_key = 'ProfitBeforeTax'       THEN f.value END) AS FLOAT) AS profit_before_tax,
    CAST(MAX(CASE WHEN a.standard_key = 'TaxExpense'            THEN f.value END) AS FLOAT) AS tax_expense,
    CAST(MAX(CASE WHEN a.standard_key = 'NetIncome'             THEN f.value END) AS FLOAT) AS net_income,
    CAST(MAX(CASE WHEN a.standard_key = 'NetIncomeParent'       THEN f.value END) AS FLOAT) AS net_income_parent,
    CAST(MAX(CASE WHEN a.standard_key = 'DepreciationAmort'     THEN f.value END) AS FLOAT) AS depreciation_amort,
    CAST(MAX(CASE WHEN a.standard_key = 'Depreciation_Memo'     THEN f.value END) AS FLOAT) AS depreciation_memo,
    CAST(MAX(CASE WHEN a.standard_key = 'OperatingCashFlow'     THEN f.value END) AS FLOAT) AS operating_cash_flow,
    CAST(MAX(CASE WHEN a.standard_key = 'CapEx'                 THEN f.value END) AS FLOAT) AS capex,
    CAST(MAX(CASE WHEN a.standard_key = 'InvestingCashFlow'     THEN f.value END) AS FLOAT) AS investing_cash_flow,
    CAST(MAX(CASE WHEN a.standard_key = 'FinancingCashFlow'     THEN f.value END) AS FLOAT) AS financing_cash_flow,
    CAST(MAX(CASE WHEN a.standard_key = 'DividendsPaid'         THEN f.value END) AS FLOAT) AS dividends_paid,
    CAST(MAX(CASE WHEN a.standard_key = 'CashEndOfPeriod'       THEN f.value END) AS FLOAT) AS cash_end_of_period
FROM dw.fact_financials f
JOIN dw.dim_company c ON c.company_key = f.company_key
JOIN dw.dim_date    d ON d.date_key    = f.date_key
JOIN dw.dim_account a ON a.account_key = f.account_key
WHERE a.standard_key IS NOT NULL
GROUP BY c.company_key, c.ticker, c.short_name,
         d.date_key, d.period_label, d.fiscal_year, d.fiscal_quarter, d.year_quarter, d.period_month;
GO

-- 2) Oranlar: marj, likidite, borçluluk, verimlilik, DuPont ---------------
CREATE OR ALTER VIEW dw.vw_ratios
AS
WITH b AS (
    SELECT s.*,
           CAST(12 AS FLOAT) / s.period_month                                   AS ann,
           s.core_operating_profit + s.depreciation_amort          AS ebitda,   -- FAVÖK = 3H + amortisman
           s.st_fin_debt + s.lt_fin_debt                           AS fin_debt,
           s.st_fin_debt + s.lt_fin_debt - s.cash - s.st_fin_investments AS net_debt,
           s.operating_cash_flow + s.capex                         AS fcf
    FROM dw.vw_std_ytd s
), c AS (
    SELECT b.*,
           CASE WHEN cogs < 0    THEN inventories       / (-cogs * ann)   * 365 END AS dio,
           CASE WHEN revenue > 0 THEN trade_receivables / (revenue * ann) * 365 END AS dso,
           CASE WHEN cogs < 0    THEN trade_payables    / (-cogs * ann)   * 365 END AS dpo
    FROM b
)
SELECT
    company_key, ticker, short_name, date_key, period_label, fiscal_year, fiscal_quarter, year_quarter,
    period_month, is_tms29,
    -- Temel büyüklükler (YTD, TL, raporlandığı gibi)
    revenue, gross_profit, core_operating_profit, operating_profit, ebitda, net_income, net_debt, fcf,
    -- Kârlılık (marjlar)
    gross_profit     / NULLIF(revenue, 0) AS gross_margin,
    ebitda           / NULLIF(revenue, 0) AS ebitda_margin,
    core_operating_profit / NULLIF(revenue, 0) AS core_operating_margin,
    operating_profit / NULLIF(revenue, 0) AS operating_margin,
    net_income       / NULLIF(revenue, 0) AS net_margin,
    -- Likidite
    current_assets / NULLIF(current_liabilities, 0)                        AS current_ratio,
    (current_assets - inventories) / NULLIF(current_liabilities, 0)        AS quick_ratio,
    (cash + st_fin_investments) / NULLIF(current_liabilities, 0)           AS cash_ratio,
    -- Borçluluk
    CASE WHEN ebitda > 0.01 * revenue THEN net_debt / (ebitda * ann) END          AS net_debt_to_ebitda,
    fin_debt / NULLIF(total_equity, 0)                                     AS fin_debt_to_equity,
    (current_liabilities + non_current_liabilities) / NULLIF(total_assets, 0) AS liabilities_to_assets,
    -- 3HC işaretli NET tutardır (negatif = gider). Yalnız net gider varken hesaplanır; net gelirde NULL.
    CASE WHEN finance_expense < 0 AND ebitda > 0.01 * revenue THEN ebitda / (-finance_expense) END     AS ebitda_to_finance_expense,
    -- Çalışma sermayesi (yıllıklandırılmış akış / dönem sonu bakiye)
    CASE WHEN inventories > 0 AND cogs < 0 THEN (-cogs * ann) / inventories END AS inventory_turnover,
    dio, dso, dpo, dio + dso - dpo AS cash_conversion_cycle,
    -- Nakit üretimi
    CASE WHEN ebitda > 0.01 * revenue THEN operating_cash_flow / ebitda END             AS ocf_to_ebitda,
    fcf / NULLIF(revenue, 0)                                               AS fcf_margin,
    -capex / NULLIF(revenue, 0)                                            AS capex_to_revenue,
    -- DuPont: ROE = net marj x varlık devri x özkaynak çarpanı (hepsi yıllıklandırılmış, dönem sonu bakiye)
    net_income / NULLIF(revenue, 0)                                        AS dupont_net_margin,
    (revenue * ann) / NULLIF(total_assets, 0)                              AS dupont_asset_turnover,
    CASE WHEN total_equity > 0 THEN total_assets / total_equity END        AS dupont_equity_multiplier,
    CASE WHEN total_equity > 0 THEN net_income * ann / total_equity END    AS roe_annualized,
    net_income * ann / NULLIF(total_assets, 0)                             AS roa_annualized
FROM c;
GO

-- 3) Çeyreklik görünüm (YTD farkıyla türetilmiş; nominal) -----------------
CREATE OR ALTER VIEW dw.vw_quarterly_std
AS
WITH q AS (
    SELECT company_key, ticker, short_name, date_key, period_label, fiscal_year, fiscal_quarter, year_quarter,
           MAX(CAST(is_tms29 AS INT)) AS is_tms29,
           CAST(MAX(CASE WHEN standard_key = 'Revenue'           THEN value_quarterly END) AS FLOAT) AS revenue_q,
           CAST(MAX(CASE WHEN standard_key = 'GrossProfit'       THEN value_quarterly END) AS FLOAT) AS gross_profit_q,
           CAST(MAX(CASE WHEN standard_key = 'CoreOperatingProfit' THEN value_quarterly END) AS FLOAT) AS core_operating_profit_q,
           CAST(MAX(CASE WHEN standard_key = 'DepreciationAmort' THEN value_quarterly END) AS FLOAT) AS depreciation_q,
           CAST(MAX(CASE WHEN standard_key = 'NetIncome'         THEN value_quarterly END) AS FLOAT) AS net_income_q,
           CAST(MAX(CASE WHEN standard_key = 'OperatingCashFlow' THEN value_quarterly END) AS FLOAT) AS operating_cash_flow_q,
           CAST(MAX(CASE WHEN standard_key = 'CapEx'             THEN value_quarterly END) AS FLOAT) AS capex_q
    FROM dw.vw_fact_quarterly
    WHERE standard_key IN ('Revenue','GrossProfit','CoreOperatingProfit','DepreciationAmort','NetIncome','OperatingCashFlow','CapEx')
    GROUP BY company_key, ticker, short_name, date_key, period_label, fiscal_year, fiscal_quarter, year_quarter
), r AS (
    SELECT q.*,
           core_operating_profit_q + depreciation_q AS ebitda_q,
           CASE WHEN EXISTS (SELECT 1 FROM dw.known_data_issues i
                             WHERE i.scope = 'QUARTERLY_DERIVATION' AND i.ticker = q.ticker
                               AND i.period_label = q.period_label) THEN 1 ELSE 0 END AS known_issue_flag
    FROM q
), w AS (
    SELECT r.*,
           LAG(revenue_q)       OVER (PARTITION BY company_key ORDER BY date_key)    AS revenue_q_prev,
           LAG(revenue_q, 4)    OVER (PARTITION BY company_key ORDER BY date_key)    AS revenue_q_yago,
           LAG(known_issue_flag)    OVER (PARTITION BY company_key ORDER BY date_key) AS prev_issue_flag,
           LAG(known_issue_flag, 4) OVER (PARTITION BY company_key ORDER BY date_key) AS yago_issue_flag
    FROM r
)
SELECT company_key, ticker, short_name, date_key, period_label, fiscal_year, fiscal_quarter, year_quarter, is_tms29,
       revenue_q, gross_profit_q, ebitda_q, core_operating_profit_q, net_income_q, operating_cash_flow_q, capex_q,
       gross_profit_q / NULLIF(revenue_q, 0) AS gross_margin_q,
       ebitda_q       / NULLIF(revenue_q, 0) AS ebitda_margin_q,
       net_income_q   / NULLIF(revenue_q, 0) AS net_margin_q,
       revenue_q / NULLIF(revenue_q_prev, 0) - 1 AS revenue_qoq_nominal,
       revenue_q / NULLIF(revenue_q_yago, 0) - 1 AS revenue_yoy_nominal,
       known_issue_flag,
       CASE WHEN known_issue_flag = 1 OR ISNULL(prev_issue_flag, 0) = 1 THEN 0 ELSE 1 END AS qoq_basis_ok,
       CASE WHEN known_issue_flag = 1 OR ISNULL(yago_issue_flag, 0) = 1 THEN 0 ELSE 1 END AS yoy_basis_ok
FROM w;
GO

-- 4) YTD büyüme (aynı dönem, bir önceki yıl) -----------------------------
CREATE OR ALTER VIEW dw.vw_growth_ytd
AS
SELECT
    cur.company_key, cur.ticker, cur.short_name, cur.date_key, cur.period_label, cur.fiscal_year,
    cur.fiscal_quarter, cur.year_quarter, cur.is_tms29,
    cur.revenue AS revenue_ytd, prv.revenue AS revenue_ytd_prev_year,
    cur.revenue / NULLIF(prv.revenue, 0) - 1 AS revenue_growth_nominal,
    cur.ebitda  / NULLIF(prv.ebitda, 0)  - 1 AS ebitda_growth_nominal,
    CASE
        WHEN EXISTS (SELECT 1 FROM dw.known_data_issues i
                     WHERE i.ticker = cur.ticker AND i.status IN ('CONFIRMED','SUSPECTED')
                       AND i.period_label IN (cur.period_label, prv.period_label)) THEN 'BASE_BREAK'
        WHEN cur.date_key >= 202312 THEN 'NOMINAL_TMS29'
        ELSE 'NOMINAL'
    END AS comparability
FROM dw.vw_ratios cur
JOIN dw.vw_ratios prv ON prv.company_key = cur.company_key AND prv.date_key = cur.date_key - 100;
GO

-- 5) Stored procedure'ler ------------------------------------------------
CREATE OR ALTER PROCEDURE dw.usp_company_ratios
    @ticker VARCHAR(10),
    @from_date_key INT = 201903,
    @to_date_key   INT = 202512
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ticker, period_label, year_quarter, is_tms29,
           revenue, gross_margin, ebitda_margin, net_margin,
           current_ratio, quick_ratio, net_debt_to_ebitda, inventory_turnover,
           dio, dso, dpo, cash_conversion_cycle, ocf_to_ebitda, roe_annualized
    FROM dw.vw_ratios
    WHERE ticker = @ticker AND date_key BETWEEN @from_date_key AND @to_date_key
    ORDER BY date_key;
END;
GO

CREATE OR ALTER PROCEDURE dw.usp_sector_snapshot
    @date_key INT
AS
BEGIN
    SET NOCOUNT ON;
    -- Sektör ortalaması = 4 şirketin basit ortalaması; sıra 1 = en iyi
    SELECT ticker, period_label,
           gross_margin,       RANK() OVER (ORDER BY gross_margin DESC)       AS gross_margin_rank,
           gross_margin - AVG(gross_margin) OVER ()                           AS gross_margin_vs_sector,
           ebitda_margin,      RANK() OVER (ORDER BY ebitda_margin DESC)      AS ebitda_margin_rank,
           ebitda_margin - AVG(ebitda_margin) OVER ()                         AS ebitda_margin_vs_sector,
           net_margin,         RANK() OVER (ORDER BY net_margin DESC)         AS net_margin_rank,
           net_margin - AVG(net_margin) OVER ()                               AS net_margin_vs_sector,
           current_ratio,      RANK() OVER (ORDER BY current_ratio DESC)      AS current_ratio_rank,
           net_debt_to_ebitda, RANK() OVER (ORDER BY net_debt_to_ebitda ASC)  AS leverage_rank,
           ocf_to_ebitda,      RANK() OVER (ORDER BY ocf_to_ebitda DESC)      AS cash_conversion_rank
    FROM dw.vw_ratios
    WHERE date_key = @date_key
    ORDER BY ticker;
END;
GO

CREATE OR ALTER PROCEDURE dw.usp_dupont
    @ticker VARCHAR(10)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT ticker, period_label, is_tms29,
           dupont_net_margin, dupont_asset_turnover, dupont_equity_multiplier,
           dupont_net_margin * dupont_asset_turnover * dupont_equity_multiplier AS roe_from_components,
           roe_annualized, roa_annualized
    FROM dw.vw_ratios
    WHERE ticker = @ticker
    ORDER BY date_key;
END;
GO

-- 6) Hızlı kontrol --------------------------------------------------------
SELECT ticker, period_label, revenue, gross_margin, ebitda_margin, net_margin, current_ratio,
       net_debt_to_ebitda, inventory_turnover, cash_conversion_cycle, ocf_to_ebitda, roe_annualized
FROM dw.vw_ratios WHERE period_label = '2025/12' ORDER BY ticker;
GO
SELECT COUNT(*) AS ratio_rows FROM dw.vw_ratios;
SELECT COUNT(*) AS quarterly_rows FROM dw.vw_quarterly_std;
SELECT COUNT(*) AS growth_rows FROM dw.vw_growth_ytd;
GO
