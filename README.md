# ⚡ NSE Stock Market Terminal & Institutional Activity Hub

A real-time Indian NSE equity screener, technical pattern scanner, and comprehensive **Institutional Smart Money Flow Hub** powered by Streamlit, SQLite, and official Indian regulatory data providers.

---

## 🚀 Key Features

### 1. 🏦 Institutional Activity & Smart Money Flow (NEW)
A dedicated, enterprise-grade institutional intelligence suite tracking Indian equities and mutual fund schemes:

- **📊 1. Overview**: Market-level institutional net activity cards (FII, MF, DII, Total across Today, 5D, 20D, 1M, 3M) with interactive Plotly daily and cumulative flow charts.
- **📈 2. MF Activity**: Daily gross equity purchases, gross sales, and net investment by Indian mutual funds across customizable time horizons (7D, 30D, 3M, 6M, 1Y).
- **🔍 3. MF Stock Scanner**: Identify equities with strong fund accumulation or distribution. Sub-perspectives include:
  - 🔥 **MF Accumulation Ranking**: Configurable accumulation scoring engine.
  - 🧲 **Multi-Fund Accumulation**: Filter stocks accumulated by $\ge N$ mutual funds ($N \ge 2, 3, 5, 10, 15, 20$).
  - 🆕 **New MF Positions**: Equities where mutual funds initiated brand-new positions ($0\% \to >0\%$).
  - 🚪 **MF Exits**: Equities completely exited by mutual funds ($>0\% \to 0\%$).
  - 🔻 **MF Distribution**: Equities with net exposure reduction across funds.
- **🏛️ 4. Fund Explorer**: Search and inspect individual mutual fund schemes (AUM, equity allocation, new additions, increases, reductions, exits, and historical stock allocation charts).
- **🔬 5. Stock Explorer**: Search any NSE stock (e.g. `BHEL`, `BEL`, `RELIANCE`) to view total MF & FII ownership %, fund-by-fund share breakdown, status badges, and interactive historical ownership charts.
- **🌍 6. FII Activity**: Daily foreign institutional investor (FII / FPI) gross buy, gross sell, and net flow metrics, alongside stock-level FII ownership tracking.
- **🧠 7. Institutional Consensus**: Multi-institutional consensus matrix combining MF, FII, and DII trends with sector-level flow tables and an interactive sector heatmap.
- **📜 8. Historical Data & Sync**: Pipeline synchronization manager with "🔄 Update Institutional Data" trigger, data freshness badges, audit logs, and direct database exports.

### 2. ⚡ Live Technical Screener Presets
- **Short Term Breakouts** (`chartink.com/screener/short-term-breakouts`)
- **Consolidated Breakout (SMA Convergence)**
- **Volume Shockers (Volume > 2x 20 SMA)**
- **20 EMA Pullback Bounce**
- **Bullish Engulfing Pattern**
- **About to Break (BTST / Bull Run)**
- **Volatility Contraction Pattern (VCP)**
- **Watchlist & Notes**: Persisted local watchlist in `watchlist.json`.

### 3. 🎯 Screener Institutional Integration
Cross-reference technical breakout candidates against institutional activity with optional sidebar filters:
- ☐ MF Holding Increased
- ☐ FII Holding Increased
- ☐ DII Buying
- ☐ MF Consensus Buying
- ☐ New MF Entry
- ☐ Multiple MF Funds Accumulating
- ☐ Institutional Accumulation

---

## 🛠️ Architecture & Data Standards

- **Official Regulatory Disclosures**: Ingests data from official sources (NSE India, AMFI, SEBI, BSE, NSDL).
- **Exact Purchase Date Limitation**: In strict compliance with regulatory standards, portfolio disclosures explicitly reflect comparisons across reporting dates. Exact intraday transaction dates are never manufactured.
- **Holding % vs Portfolio Weight %**: Clearly separates equity share in the company from the stock's weight within a fund's portfolio.
- **Preserved Historical Data**: SQLite database (`data/institutional.db`) retains complete multi-period disclosure history without overwriting past reporting periods.

---

## 🏃 Running the Application

1. Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

2. Run automated test suite:
   ```bash
   python -m pytest tests/ -v
   ```

3. Launch the Streamlit dashboard:
   ```bash
   python -m streamlit run app.py
   ```

4. Use the sidebar navigation to switch between **⚡ Live Technical Screener** and **🏦 Institutional Activity**.

---

## 📖 Detailed Documentation
For deep-dive methodology, database schemas, scoring formulas, and data pipeline documentation, consult:
[`docs/institutional_activity.md`](docs/institutional_activity.md).
