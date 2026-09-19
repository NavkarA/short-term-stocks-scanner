# 🏦 Institutional Activity Module Documentation

## 1. Overview & Architecture

The **Institutional Activity** module is an enterprise-grade analytics suite seamlessly integrated into the Python/Streamlit Indian Stock Market Terminal. It tracks, analyzes, and cross-references institutional equity behavior across:

- **Mutual Funds (MF)**: Monthly portfolio disclosures, equity holdings, fund additions, reductions, new positions, and complete exits.
- **Foreign Institutional Investors (FII / FPI)**: Daily gross purchases, gross sales, net trading flows, and quarterly shareholding ownership patterns.
- **Domestic Institutional Investors (DII)**: Daily gross and net equity market activity.
- **Institutional Consensus**: Multi-institution synthesis and sector-level flow heatmaps.
- **Screener Integration**: Optional institutional confirmation filters directly inside technical breakout screeners.

```
                    ┌─────────────────────────────────────────┐
                    │      Official Indian Data Sources       │
                    │  (NSE India, AMFI, SEBI, BSE, NSDL)     │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │    Institutional Data Provider Layer    │
                    │  (Session reuse, Backoff, Rate Limits)  │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │     Validation & Deduplication Engine   │
                    │  (0-100% bounds, ISIN check, Dates)     │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │       SQLite Historical Database        │
                    │  (WAL Mode, Indexed, History Preserved) │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │       Calculations & Scoring Engine     │
                    │  (Holding diffs, Statuses, Consensus)   │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
      ┌───────────────────────────┐             ┌───────────────────────────┐
      │  🏦 Institutional Hub UI  │             │  ⚡ Screener Integration  │
      │  (8 Interactive Sub-Tabs) │             │  (Institutional Filters)  │
      └───────────────────────────┘             └───────────────────────────┘
```

---

## 2. Official Data Sources & Frequency

| Source | Identifier | Description | Reporting Frequency |
|---|---|---|---|
| **NSE India** | `NSE` | Daily FII/DII gross buy, gross sell, and net investment (`api/fiidiiTradeReact`). Quarterly shareholding patterns. | Daily (Market Days ~18:30 IST) & Quarterly |
| **AMFI India** | `AMFI` | Monthly mutual fund scheme portfolio disclosures, scheme AUM, and NAV data. | Monthly (by 10th of following month) |
| **SEBI** | `SEBI` | Regulatory aggregate mutual fund investment in equity and debt. | Daily / Monthly |
| **BSE India** | `BSE` | Shareholding pattern disclosures and bulk/block deal filings. | Quarterly / As filed |
| **NSDL / CDSL** | `NSDL` | Foreign Portfolio Investor (FPI) trends and sector assets under custody. | Fortnightly / Monthly |

---

## 3. Database Schema

Stored in SQLite (`data/institutional.db`) with WAL mode enabled and strict indexing.

### `mf_holdings_history`
Preserves historical disclosures over time without overwriting.
- `id`: Primary key integer.
- `fund_id`: Unique mutual fund scheme code (e.g. `QUANT_PSU`, `HDFC_TOP100`).
- `fund_name`: Full scheme name.
- `amc_name`: Asset Management Company name.
- `stock_symbol`: NSE equity ticker (e.g. `BHEL`, `BEL`).
- `isin`: International Securities Identification Number (e.g. `INE257A01026`).
- `reporting_date`: Date of portfolio snapshot (`YYYY-MM-DD`).
- `shares`: Number of equity shares held (or `NULL` if unavailable).
- `holding_percent`: Percentage of company's equity held (`0.0` to `100.0`).
- `portfolio_weight`: Percentage of scheme's portfolio allocated to this stock (`0.0` to `100.0`).
- `market_value`: Market value of holding in ₹ Crores.
- `source`: Attribution (`AMFI`, etc.).
- `source_url`: URL of source disclosure.
- `retrieved_at`: Ingestion timestamp.
- **Constraints**: `UNIQUE(fund_id, isin, reporting_date)`.
- **Indexes**: `stock_symbol`, `fund_id`, `reporting_date`, `isin`.

### `institutional_daily_activity`
- `id`: Primary key integer.
- `activity_date`: Date of trading activity (`YYYY-MM-DD`).
- `institution_type`: `FII`, `DII`, or `MF`.
- `gross_buy`: Total purchase value in ₹ Crores.
- `gross_sell`: Total sales value in ₹ Crores.
- `net_activity`: Net flow in ₹ Crores (`gross_buy - gross_sell`).
- `source`: Attribution (`NSE`, `SEBI`).
- **Constraints**: `UNIQUE(activity_date, institution_type)`.

### `fii_holdings_history`
- `id`: Primary key integer.
- `stock_symbol`: NSE ticker.
- `isin`: ISIN code.
- `reporting_date`: End of quarter/month date (`YYYY-MM-DD`).
- `holding_percent`: Percentage of company's equity held by FIIs.
- **Constraints**: `UNIQUE(stock_symbol, reporting_date)`.

### `data_update_log`
- `id`: Primary key integer.
- `source_name`: `AMFI`, `NSE`, `SEBI`, etc.
- `update_type`: Job name.
- `status`: `SUCCESS`, `DELAYED`, `FAILED`.
- `records_updated`: Number of records processed.
- `error_message`: Debugging details if failed.
- `timestamp`: Execution timestamp.

---

## 4. Key Calculation Methodologies & Semantics

### Critical Semantic Distinction: Holding % vs. Portfolio Weight %
- **Holding %**: Percentage of the company's total outstanding equity shares held by the fund.
  $$\text{Holding \%} = \frac{\text{Shares held by Fund}}{\text{Total Company Outstanding Shares}} \times 100$$
- **Portfolio Weight %**: Percentage of the mutual fund's total assets under management invested in this stock.
  $$\text{Portfolio Weight \%} = \frac{\text{Value of Stock Position in Fund}}{\text{Total Fund AUM}} \times 100$$

### Holding Change vs Relative Change
1. **Percentage Points Change**:
   $$\Delta_{\text{pp}} = \text{Current Holding \%} - \text{Previous Holding \%}$$
   *Example: 5.0% to 7.0% is **+2.00 percentage points**.*
2. **Relative Change**:
   $$\Delta_{\text{rel}} = \left(\frac{\text{Current Holding \%}}{\text{Previous Holding \%}} - 1\right) \times 100$$
   *Example: 5.0% to 7.0% is a **+40.0% relative increase**.*

### Position Classification Logic
Comparing holdings between previous reporting date $T_{-1}$ and current reporting date $T_0$:
- **`NEW`**: Previous $\le 0.0001\%$ and Current $> 0.0001\%$.
- **`EXITED`**: Previous $> 0.0001\%$ and Current $\le 0.0001\%$.
- **`INCREASED`**: Current $>$ Previous $+ 0.0001\%$.
- **`REDUCED`**: Current $<$ Previous $- 0.0001\%$.
- **`UNCHANGED`**: Absolute difference $\le 0.0001\%$.

### Accumulation Score Model
Configurable institutional accumulation metric normalized to a 0–100 scale (50 is neutral):
$$\text{Raw Score} = w_{\text{inc}} \cdot I(\Delta > 0) + w_{\text{new}} \cdot N_{\text{new}} + w_{\text{dec}} \cdot I(\Delta < 0) + w_{\text{exit}} \cdot N_{\text{exit}} + w_{\text{m\_inc}} \cdot N_{\text{inc}} + w_{\text{m\_dec}} \cdot N_{\text{dec}}$$
Default weights:
- Holding increase: $+2.0$
- New entry: $+3.0$
- Holding decrease: $-2.0$
- Complete exit: $-3.0$
- Each fund increasing: $+1.0$
- Each fund decreasing: $-1.0$
- Significant change ($>1.0$ pp): $\pm 2.0$

---

## 5. Exact Purchase Date Limitation (Compliance Notice)

Indian mutual fund disclosures are mandated by SEBI to be reported on a **monthly periodic basis** (as of the last calendar day of the month).

> [!IMPORTANT]
> **Strict Compliance**:
> - The application clearly presents holding movements between reporting periods (e.g. *"Holding increased between 31-Jul-2024 and 31-Aug-2024"*).
> - The system **never manufactures fake or inferred intraday purchase dates**.
> - Exact transaction dates are only displayed if an official exchange filing (e.g. bulk/block deal) explicitly documents an exchange transaction.

---

## 6. Configuration & Environment Variables

Configure via environment variables or a `.env` file:

```env
# Enable/disable institutional module
INSTITUTIONAL_DATA_ENABLED=true

# Provider update toggles
MF_UPDATE_ENABLED=true
FII_UPDATE_ENABLED=true
DII_UPDATE_ENABLED=true

# Cache and rate limit settings
INSTITUTIONAL_CACHE_TTL=86400
INSTITUTIONAL_REQUEST_TIMEOUT=20
INSTITUTIONAL_MAX_RETRIES=3
INSTITUTIONAL_BACKOFF_FACTOR=2.0

# Database path (defaults to data/institutional.db)
INSTITUTIONAL_DB_PATH=data/institutional.db
```

---

## 7. Troubleshooting & Error Resilience

- **NSE API Throttling**: The NSE data provider automatically manages browser headers, user agents, and session cookies. If the NSE endpoint returns 401/403 or market is closed, the application gracefully logs the status as `DELAYED` without crashing or clearing existing historical data.
- **AMFI Disclosures**: Disclosures are updated on monthly cycles. Historical records remain permanently queryable.
- **Offline / Isolated Environments**: The system automatically initializes and seeds verified baseline disclosures for major Indian equities on first run.
