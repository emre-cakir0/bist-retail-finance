# RetailFinance - Power BI dashboard şablonu

Bu dosya `measures.dax` ile birlikte kullanılır. `.pbix` dosyasını Power BI Desktop'ta bu şablona göre oluştur.

## 1) Bağlantı ve model

1. **Veriyi Al > SQL Server**, sunucu `localhost\SQLEXPRESS`, veritabanı `RetailFinance`, **Import** modu.
2. Şu nesneleri seç ve yanındaki adlarla yeniden adlandır:

| SQL nesnesi | Power BI tablo adı | Rolü |
|---|---|---|
| `dw.dim_company` | `dim_company` | Boyut |
| `dw.dim_date` | `dim_date` | Boyut |
| `dw.vw_ratios` | `fact_ratios` | Olgu: şirket x dönem, YTD oranlar |
| `dw.vw_quarterly_std` | `fact_quarterly` | Olgu: şirket x çeyrek (nominal) |
| `dw.vw_growth_ytd` | `fact_growth` | Olgu: YTD büyüme (nominal) |
| `dw.known_data_issues` | `known_issues` | İlişkisiz, uyarılar için |
| `dw.dq_results` | `dq_results` | İlişkisiz, kalite kartları için |

3. **İlişkiler** (çoktan-bire, tek yön): `fact_ratios`, `fact_quarterly`, `fact_growth` tablolarının `company_key` alanı `dim_company[company_key]` ile, `date_key` alanı `dim_date[date_key]` ile eşlenir. `known_issues` ve `dq_results` ilişkisiz kalır.
4. `dim_date` tablosuna hesaplanmış sütun ekle: `period_index = dim_date[fiscal_year] * 4 + dim_date[fiscal_quarter]`.
5. `dim_date[period_label]` sütununu `dim_date[date_key]` ile sırala.
6. `measures.dax` içindeki ölçüleri ayrı bir `_Measures` tablosuna yapıştır.

Tablo büyüklükleri küçüktür (en büyüğü 112 satır), performans kaygısı yoktur.

## 2) Sayfalar (3 sayfa)

Tüm sayfalarda üstte **Şirket** slicer'ı (`dim_company[short_name]`, çoklu seçim) ve **Dönem** slicer'ı (`dim_date[period_label]`, tek seçim, varsayılan `2025/12`) bulunur. Slicer'ları **Görünüm > Slicer'ları eşitle** ile üç sayfada eşitle: şirket slicer'ı tüm sayfaları günceller.

### Sayfa 1: Sektör özeti (büyüme ve marj)
- **Kartlar:** `Revenue YTD (TL bn)`, `Gross Margin`, `EBITDA Margin`, `Net Margin` (sektör ortalaması için şirket slicer'ı boş bırakılır).
- **Kümelenmiş sütun:** eksen `dim_company[short_name]`, değerler `Gross Margin`, `EBITDA Margin`, `Net Margin`.
- **Çizgi grafik:** eksen `dim_date[period_label]`, değer `EBITDA Margin`, açıklama `dim_company[short_name]`. Bu grafik YTD marjı gösterir (aynı kolon içi, güvenilir).
- **Tablo:** şirket, `Revenue YTD (TL bn)`, `Revenue Growth YoY (nominal)`, `Growth Comparability`, `Gross Margin Rank`, `EBITDA Margin Rank`, `Net Margin Rank`.
- **Uyarı kutusu:** `TMS29 Banner`, `Growth Banner`.
- Koşullu biçim: `Growth Comparability = "BASE_BREAK"` olan satırlarda büyüme hücresini gri yap (değeri göstermek yanıltıcıdır).

### Sayfa 2: Şirket detayı (trend, oranlar, DuPont)
- Şirket tek seçimli kullanılır.
- **Çizgi grafikler:** `Gross Margin`, `EBITDA Margin`, `Net Margin` zaman içinde.
- **DuPont tablosu:** dönem satırlarında `DuPont Net Margin`, `DuPont Asset Turnover`, `DuPont Equity Multiplier`, `ROE (annualized)`. Çarpım ROE'ye eşittir.
- **Çalışma sermayesi:** sütun grafik `DIO (days)`, `DSO (days)`, `DPO (days)`, çizgi `Cash Conversion Cycle (days)`.
- **Nakit üretimi:** `OCF to EBITDA`, `FCF Margin`.
- **Çeyreklik grafik (isteğe bağlı):** `Revenue Q`, `EBITDA Margin Q`. Çeyreklik türetme nominaldir; `Quarter Basis OK = 0` olan çeyrekleri farklı renkle göster ve dipnot ekle.
- **Uyarı kutusu:** `Data Issue Banner`, `TMS29 Banner`.

### Sayfa 3: Likidite ve borçluluk
- **Çizgi grafik:** `Current Ratio`, `Quick Ratio`, `Cash Ratio` zaman içinde.
- **Çizgi/sütun:** `Net Debt to EBITDA`, `Fin Debt to Equity`.
- **Dağılım grafiği:** x `Net Debt to EBITDA`, y `ROE (annualized)`, balon `short_name`.
- **Tablo:** `Current Ratio`, `Net Debt to EBITDA`, `Leverage Rank (1 = lowest)`, `Cash Conversion Rank`.
- **Boş değer notu:** FAVÖK marjı %1'in altındaysa veya özkaynak negatifse ilgili oranlar bilerek boştur (anlamsız).

## 3) Veri kalitesi şeridi (her sayfanın altında)
Kartlar: `DQ Total Checks`, `DQ Pass`, `DQ Explained`, `DQ Fail`. Beklenen değerler: 381, 369, 12, 0.

## 4) Dashboard'da mutlaka bulunması gereken dipnotlar
1. "Değerler İş Yatırım (isyatirimhisse, resmî olmayan kaynak) verisinden alınmıştır; kritik rakamlar KAP ile doğrulanmalıdır."
2. "TMS 29 (2023/12 ve sonrası): kolonlar arası büyüme ve çeyreklik farklar nominaldir. Marj, likidite ve kaldıraç oranları aynı dönem kolonu içinde hesaplandığı için bu sorundan etkilenmez."
3. "2022/12, 2025/9 ve 2025/12 kolonlarında kaynak veri baz kırılması gösterir (dw.known_data_issues)."
