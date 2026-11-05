# RetailFinance - Veri modeli (ER diyagramı)

GitHub ve VS Code (Markdown Preview Mermaid Support eklentisi) bu diyagramı doğrudan çizer.

```mermaid
erDiagram
    STG_RAW_FINANCIALS {
        bigint load_id PK
        varchar symbol
        varchar item_code
        nvarchar item_name_tr
        nvarchar item_name_en
        varchar period_label
        float raw_value
        varchar source_file
    }
    DIM_COMPANY {
        int company_key PK
        varchar ticker UK
        nvarchar short_name
        varchar financial_group
        date tms29_start_date
        nvarchar tms29_source
    }
    DIM_DATE {
        int date_key PK "YYYYMM, ör. 202512"
        date period_end_date
        smallint fiscal_year
        tinyint fiscal_quarter
        tinyint period_month "3, 6, 9, 12"
        varchar period_label "2019/3"
        bit is_tms29_era
    }
    DIM_ACCOUNT {
        int account_key PK
        varchar account_code UK "kaynak kalem kodu"
        nvarchar account_name
        varchar statement_type "BS, IS, CF, MEMO"
        bit is_cumulative
        varchar standard_key "Revenue, COGS, TotalAssets ..."
        varchar value_kind
    }
    FACT_FINANCIALS {
        bigint fact_id PK
        int company_key FK
        int date_key FK
        int account_key FK
        decimal value "raporlandığı gibi (YTD)"
        bit is_tms29
    }
    MAP_STANDARD_ACCOUNT {
        varchar standard_key PK
        varchar account_code UK
        varchar statement_group
        nvarchar sign_note
    }
    KNOWN_DATA_ISSUES {
        int issue_id PK
        varchar ticker
        varchar period_label
        varchar scope
        varchar status
    }
    DQ_RESULTS {
        int result_id PK
        varchar test_name
        varchar ticker
        varchar period_label
        varchar result "PASS, EXPLAINED, FAIL"
    }

    DIM_COMPANY ||--o{ FACT_FINANCIALS : "company_key"
    DIM_DATE    ||--o{ FACT_FINANCIALS : "date_key"
    DIM_ACCOUNT ||--o{ FACT_FINANCIALS : "account_key"
    MAP_STANDARD_ACCOUNT ||--o| DIM_ACCOUNT : "standard_key / account_code"
    STG_RAW_FINANCIALS }o--|| DIM_COMPANY : "symbol = ticker"
    STG_RAW_FINANCIALS }o--|| DIM_ACCOUNT : "item_code = account_code"
    STG_RAW_FINANCIALS }o--|| DIM_DATE : "period_label"
    KNOWN_DATA_ISSUES }o--o| DIM_COMPANY : "ticker (boş = tümü)"
```

## Katmanlar

| Katman | Nesneler | Not |
|---|---|---|
| Staging (`stg`) | `raw_financials` | CSV'nin uzun formata çevrilmiş, değiştirilmemiş hali |
| Veri ambarı (`dw`) | `dim_company`, `dim_date`, `dim_account`, `fact_financials` | Yıldız şema; değerler raporlandığı gibi (kümülatif) saklanır |
| Eşleştirme | `map_standard_account` | 147 kaynak kalemden 36 standart anahtar |
| Analiz | `vw_std_ytd`, `vw_ratios`, `vw_fact_quarterly`, `vw_quarterly_std`, `vw_growth_ytd` | Oranlar aynı dönem kolonu içinde hesaplanır |
| Prosedürler | `usp_load_financials`, `usp_company_ratios`, `usp_sector_snapshot`, `usp_dupont`, `usp_run_quality_checks` | |
| Kalite | `dq_results`, `vw_dq_summary`, `known_data_issues` | Test sonuçları ve belgelenmiş istisnalar |
