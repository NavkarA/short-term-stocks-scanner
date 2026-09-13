# ⚡ Chartink Live Screener Streamlit Dashboard

A real-time Indian NSE stock screener and monitoring dashboard powered by **Chartink scraping** and **Streamlit**.

---

## 🚀 Key Features

### 1. 🏛️ Curated Screener Presets
- **Short Term Breakouts** (`chartink.com/screener/short-term-breakouts`):
  - 5-day highest close breaks 1.05x (5% above) 120-day high close, with volume expanding above the 5-day SMA volume on green daily closes.
- **Consolidated Breakout (SMA Convergence)**:
  - Tight Bollinger/MA compression within ±3% of 5, 20, 50, 100, and 200 SMAs.
- **Volume Shockers**:
  - Today's volume > 2x 20-day average volume on green candles.
- **20 EMA Pullback Bounce**:
  - Stage-2 uptrend stocks testing the 20 EMA and bouncing back.
- **Bullish Engulfing Pattern** (`chartink.com/screener/bullish-engulfing-pattern-1`):
  - Daily Bullish Engulfing: Green candle completely engulfs previous red candle body, high, and low.
- **About to Break (BTST / Bull Run)** (`chartink.com/screener/about-to-break-1`):
  - Supertrend(7,1) within ₹10 of close, daily volume > 20 SMA, and 3 consecutive 5-minute higher highs with volume momentum.
- **Volatility Contraction Pattern (VCP)** (`chartink.com/screener/volatility-compression`):
  - Mark Minervini VCP setup: Multi-timeframe trend alignment (weekly EMA 13 > 26 > SMA 50), tight volatility compression near 50-week highs.

### 2. 📊 Real-Time Scanner Results
- Dynamic KPI metrics: Total Scanned, Top Gainer, Top Loser, Average % Change, Total Volume.
- Filter by % change (Gainers / Losers), price range, minimum volume, and company ticker.
- Shows 100% of raw scanned stocks by default (no hidden stocks).
- Direct links to **TradingView ↗** and **Chartink ↗**.
- One-click CSV export.
- Bookmark candidate stocks directly to local watchlist with trade notes.

### 3. 🛠️ Custom Scanner Studio & URL Parser
- **Auto-Fetch from URL**: Simply paste any Chartink screener URL (e.g. `https://chartink.com/screener/...`) and click **"Fetch Scanner Clause"** to automatically parse its logic.
- **Raw Clause Editor**: Edit or paste raw Chartink `scan_clause` payloads directly.

### 4. 📋 Local Watchlist
- Bookmarked stocks and personal notes stored locally in `watchlist.json`.
- Export watchlist as CSV.

---

## 🛠️ Setup & Running

1. Open your terminal in this project directory:
   ```bash
   cd c:\PY_files\strategy1
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the Streamlit dashboard:
   ```bash
   python -m streamlit run app.py
   ```

   *(If port 8501 is already in use, run with: `python -m streamlit run app.py --server.port=8502`)*
