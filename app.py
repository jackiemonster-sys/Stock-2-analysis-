import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 1. 頁面設定
st.set_page_config(page_title="台股三合一全方位分析", layout="wide")

st.title("📈 台股全方位分析系統 (籌碼/信用交易強化版)")
st.caption("結合技術面 (均線/MACD/KDJ)、深度籌碼面 (三大法人/融資融券/動能) 與基本面的智慧評估")

# 2. 獲取台股上市櫃股票清單 (支援名稱與代號雙向搜尋)
@st.cache_data(ttl=86400)
def get_taiwan_stock_list():
    try:
        # 從 FinMind 獲取完整的上市櫃股票清單
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, timeout=5)
        data = res.json()
        if data.get("status") == 200 and data.get("data"):
            df_info = pd.DataFrame(data["data"])
            # 過濾上市與上櫃股票
            df_info = df_info[df_info['industry_category'].notna()]
            
            # 建立選單顯示格式： "2330 台積電 (上市)" 或 "6547 高端疫苗 (上櫃)"
            options = []
            stock_map = {} # 用於反查詳細資訊
            
            for _, row in df_info.iterrows():
                sid = str(row['stock_id']).strip()
                sname = str(row['stock_name']).strip()
                stype = str(row['type']).strip() # 上市 / 上櫃
                
                # 轉成 yfinance 後綴
                suffix = ".TW" if stype == "上市" else ".TWO"
                ticker_symbol = f"{sid}{suffix}"
                
                label = f"{sid} {sname} ({stype})"
                options.append(label)
                stock_map[label] = {
                    "stock_id": sid,
                    "stock_name": sname,
                    "ticker_symbol": ticker_symbol,
                    "market_type": stype
                }
            return options, stock_map
    except Exception:
        pass
    
    # 預設備用選單 (若 API 抓取失敗時退回熱門股)
    default_options = [
        "2330 台積電 (上市)", "2317 鴻海 (上市)", "2454 聯發科 (上市)",
        "2382 廣達 (上市)", "2308 台達電 (上市)", "8069 元太 (上櫃)"
    ]
    default_map = {
        "2330 台積電 (上市)": {"stock_id": "2330", "stock_name": "台積電", "ticker_symbol": "2330.TW", "market_type": "上市"},
        "2317 鴻海 (上市)": {"stock_id": "2317", "stock_name": "鴻海", "ticker_symbol": "2317.TW", "market_type": "上市"},
        "2454 聯發科 (上市)": {"stock_id": "2454", "stock_name": "聯發科", "ticker_symbol": "2454.TW", "market_type": "上市"},
        "2382 廣達 (上市)": {"stock_id": "2382", "stock_name": "廣達", "ticker_symbol": "2382.TW", "market_type": "上市"},
        "2308 台達電 (上市)": {"stock_id": "2308", "stock_name": "台達電", "ticker_symbol": "2308.TW", "market_type": "上市"},
        "8069 元太 (上櫃)": {"stock_id": "8069", "stock_name": "元太", "ticker_symbol": "8069.TWO", "market_type": "上櫃"}
    }
    return default_options, default_map

stock_options, stock_map = get_taiwan_stock_list()

# 主頁面查詢區塊
st.markdown("### 🔍 股票查詢")

selected_stock_label = st.selectbox(
    "輸入股票代號或中文名稱進行搜尋（支援搜尋自動完成）",
    options=stock_options,
    index=0,
    help="例如可直接輸入 '2330' 或 '台積電'"
)

# 解析選取的股票資訊
selected_info = stock_map[selected_stock_label]
stock_id = selected_info["stock_id"]
stock_name = selected_info["stock_name"]
ticker_symbol = selected_info["ticker_symbol"]

# 抓取 FinMind 三大法人與融資融券資料
@st.cache_data(ttl=3600)
def fetch_finmind_chip_data(stock_id):
    start_date = (datetime.date.today() - datetime.timedelta(days=35)).strftime("%Y-%m-%d")
    result = {"inst": None, "margin": None}
    
    # 1. 抓取三大法人
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        param_inst = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date
        }
        res = requests.get(url, params=param_inst, timeout=5)
        data = res.json()
        if data.get("status") == 200 and data.get("data"):
            df_inst = pd.DataFrame(data["data"])
            df_inst['buy_sell'] = (df_inst['buy'] - df_inst['sell']) / 1000
            recent_inst = df_inst.groupby('name')['buy_sell'].sum().round(0).to_dict()
            result["inst"] = recent_inst
    except Exception:
        pass

    # 2. 抓取融資融券
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        param_margin = {
            "dataset": "TaiwanStockMarginPurchaseShortSale",
            "data_id": stock_id,
            "start_date": start_date
        }
        res = requests.get(url, params=param_margin, timeout=5)
        data = res.json()
        if data.get("status") == 200 and data.get("data"):
            df_margin = pd.DataFrame(data["data"])
            if not df_margin.empty:
                df_margin['date'] = pd.to_datetime(df_margin['date'])
                df_margin = df_margin.sort_values('date')
                
                recent_5d = df_margin.tail(5)
                margin_buy_change = recent_5d['MarginPurchaseBuy'].sum() - recent_5d['MarginPurchaseSell'].sum()
                short_sell_change = recent_5d['ShortSaleBuy'].sum() - recent_5d['ShortSaleSell'].sum()
                
                latest_margin = df_margin.iloc[-1]
                
                result["margin"] = {
                    "margin_today_balance": latest_margin.get("MarginPurchaseTodayBalance", 0),
                    "short_today_balance": latest_margin.get("ShortSaleTodayBalance", 0),
                    "margin_5d_change": margin_buy_change,
                    "short_5d_change": short_sell_change,
                    "df_margin": df_margin
                }
    except Exception:
        pass

    return result

@st.cache_data(ttl=3600)
def load_stock_data(symbol):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)
    
    if df.empty:
        return None, None
        
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # 技術指標計算
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    df['Vol_MA20'] = df['Volume'].rolling(window=20).mean()
    
    # MACD 指標
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['MACD_Signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['MACD_Signal']
    
    # KDJ 指標計算 (預設 N=9, M1=3, M2=3)
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    # 籌碼面衍生指標 (OBV)
    df['OBV'] = ((df['Close'].diff() > 0).astype(int) * 2 - 1) * df['Volume']
    df['OBV'] = df['OBV'].fillna(0).cumsum()
    df['OBV_MA10'] = df['OBV'].rolling(window=10).mean()

    info = ticker.info
    return df, info

df, info = load_stock_data(ticker_symbol)
chip_data = fetch_finmind_chip_data(stock_id)

if df is None or len(df) < 60:
    st.error("⚠️ 查無此股票數據，請確認股票代號或市場類型是否正確！")
else:
    latest = df.iloc[-1]
    prev_latest = df.iloc[-2]
    
    prev_close = float(prev_latest['Close'])
    close_price = float(latest['Close'])
    price_change = close_price - prev_close
    pct_change = (price_change / prev_close) * 100
    
    ma5, ma20, ma60 = float(latest['MA5']), float(latest['MA20']), float(latest['MA60'])
    dif, macd_signal, macd_hist = float(latest['DIF']), float(latest['MACD_Signal']), float(latest['MACD_Hist'])
    prev_hist = float(prev_latest['MACD_Hist'])
    vol_ratio = float(latest['Volume'] / latest['Vol_MA5']) if latest['Vol_MA5'] > 0 else 1.0

    pe_ratio = info.get('trailingPE', None) if info else None
    pb_ratio = info.get('priceToBook', None) if info else None
    dividend_yield = (info.get('dividendYield', 0) or 0) * 100 if info else 0
    eps = info.get('trailingEps', None) if info else None

    # 3. 核心卡片
    st.markdown("---")
    st.subheader(f"📊 {stock_name} ({ticker_symbol}) 核心指標")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新收盤價", f"{close_price:.2f} 元", f"{pct_change:+.2f}%")
    c2.metric("本益比 (P/E)", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
    c3.metric("股價淨值比 (P/B)", f"{pb_ratio:.2f}" if pb_ratio else "N/A")
    c4.metric("殖利率", f"{dividend_yield:.2f}%" if dividend_yield > 0 else "N/A")

    # 4. 分析邏輯：技術、基本、進階籌碼
    
    # (A) 技術面
    tech_reasons = []
    if close_price > ma5 > ma20 > ma60:
        tech_status, color = "強勢上升趨勢 🚀", "red"
        tech_desc = "均線呈現標準多頭排列，股價站穩所有均線之上。"
    elif close_price < ma5 < ma20 < ma60:
        tech_status, color = "明確下跌趨勢 📉", "green"
        tech_desc = "均線呈空頭排列，下行風險相對較高。"
    else:
        tech_status, color = "盤整震盪階段 ⚖️", "orange"
        tech_desc = "股價於均線間交織，方向性尚未完全確立。"

    if dif > macd_signal and prev_hist <= 0 and macd_hist > 0:
        tech_reasons.append("**MACD 黃金交叉**：短線多頭攻擊訊號顯著。")
    elif dif < macd_signal and prev_hist >= 0 and macd_hist < 0:
        tech_reasons.append("**MACD 死亡交叉**：短線有修正調整壓力。")
    elif macd_hist > 0:
        tech_reasons.append(f"**MACD 偏多**：柱狀體({macd_hist:+.2f}) 保持正值。")
    else:
        tech_reasons.append(f"**MACD 偏空**：柱狀體({macd_hist:+.2f}) 為負值。")

    # KDJ 現況判讀
    k_val, d_val = latest['K'], latest['D']
    if k_val > 80 and d_val > 80:
        tech_reasons.append(f"**KDJ 高檔鈍化 (K:{k_val:.1f}, D:{d_val:.1f})**：過熱區域，留意回檔或強勢飆股特徵。")
    elif k_val < 20 and d_val < 20:
        tech_reasons.append(f"**KDJ 低檔築底 (K:{k_val:.1f}, D:{d_val:.1f})**：落入超賣區，關注反彈買點。")

    # (B) 強化籌碼面評估 (法人 + 融資融券)
    chip_reasons = []
    chip_score = 0
    
    # B1: 法人籌碼
    inst_data = chip_data.get("inst")
    if inst_data:
        foreign = inst_data.get("Foreign_Investor", 0)
        investment_trust = inst_data.get("Investment_Trust", 0)
        
        chip_reasons.append(f"**近 5 日外資買賣**：{foreign:+,.0f} 張")
        chip_reasons.append(f"**近 5 日投信買賣**：{investment_trust:+,.0f} 張")
        
        if foreign > 0 and investment_trust > 0:
            chip_reasons.append("🔥 **法人同買**：外資與投信聯手加碼，籌碼集中度極佳。")
            chip_score += 2
        elif foreign < 0 and investment_trust < 0:
            chip_reasons.append("⚠️ **法人同賣**：三大法人持續提款，籌碼面受壓。")
            chip_score -= 2

    # B2: 融資融券籌碼
    margin_info = chip_data.get("margin")
    if margin_info:
        m_change = margin_info["margin_5d_change"]
        s_change = margin_info["short_5d_change"]
        m_balance = margin_info["margin_today_balance"]
        s_balance = margin_info["short_today_balance"]

        chip_reasons.append(f"**近 5 日融資增減**：{m_change:+,.0f} 張 (現有 {m_balance:,.0f} 張)")
        chip_reasons.append(f"**近 5 日融券增減**：{s_change:+,.0f} 張 (現有 {s_balance:,.0f} 張)")

        if price_change > 0 and m_change < 0:
            chip_reasons.append("✨ **價漲資減**：主力鎖碼或籌碼沉澱，散戶解套退場（籌碼健康）。")
            chip_score += 1
        elif price_change > 0 and m_change > 0:
            chip_reasons.append("⚠️ **價漲資增**：散戶追高意願強或主力開槓桿，留意追高風險。")
        elif price_change < 0 and m_change > 0:
            chip_reasons.append("🚨 **價跌資增**：散戶逢低承接套牢，籌碼趨於沉重（不利多頭）。")
            chip_score -= 1.5
        
        if s_change > 0 and price_change > 0:
            chip_reasons.append("📈 **券資同步/軋空潛力**：融券增加且股價上揚，具備軋空行情想像空間。")
            chip_score += 1

    # B3: 量價結構與 OBV
    obv_now = latest['OBV']
    obv_ma = latest['OBV_MA10']
    if obv_now > obv_ma:
        chip_reasons.append("**OBV 能量潮偏多**：資金持續淨流入。")
        chip_score += 0.5
    else:
        chip_reasons.append("**OBV 能量潮偏空**：資金呈淨流出狀態。")
        chip_score -= 0.5

    if chip_score >= 2:
        chip_status = "籌碼高度集中 (強烈偏多) 🔥"
    elif chip_score <= -2:
        chip_status = "籌碼鬆動渙散 (偏空控盤) ❄️"
    else:
        chip_status = "籌碼中性/換手洗盤 🔄"

    # (C) 基本面
    fund_reasons = []
    if eps:
        fund_reasons.append(f"**近四季 EPS**：{eps:.2f} 元")
    if pe_ratio:
        if pe_ratio < 12:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：處於低估區間。")
        elif pe_ratio > 25:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：市場給予較高溢價。")
        else:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：估值合理。")
    if dividend_yield >= 5:
        fund_reasons.append(f"**高殖利率**：{dividend_yield:.2f}%，提供下檔支撐。")

    # 5. 走勢預測
    if "強勢" in tech_status and chip_score >= 1:
        pred_week = "技術面與籌碼面（含資券結構）呈現強勢共振，短線站穩 MA5 有機會持續走揚。"
    elif "下跌" in tech_status or chip_score <= -2:
        pred_week = "籌碼面或技術面承壓，融資套牢或法人賣壓未消退前宜謹慎觀望。"
    else:
        pred_week = "籌碼呈現觀望換手，預計於均線之間區間高低震盪打底。"

    pred_month = "中線格局觀察季線 (MA60) 支撐力道，若籌碼持續沉澱且未跌破季線，中長期上升軌道不變。" if close_price > ma60 else "受制於季線 (MA60) 反壓，籌碼尚待時間消化上方套牢賣壓。"

    # 6. 三面向綜合分析報告
    st.markdown("---")
    st.subheader("📌 三面向綜合分析報告")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown(f"#### 📈 **技術面現況**")
        st.markdown(f"**狀態：:{color}[{tech_status}]**")
        st.write(tech_desc)
        st.markdown("**重點觀察：**")
        for r in tech_reasons:
            st.markdown(f"- {r}")

    with col_b:
        st.markdown("#### 💰 **籌碼面動態 (三大法人/融資融券)**")
        st.markdown(f"**狀態：{chip_status}**")
        st.markdown("**法人與資券變化：**")
        for r in chip_reasons:
            st.markdown(f"- {r}")

    with col_c:
        st.markdown("#### 🏛️ **基本面估值**")
        st.markdown("**財務體質：**")
        if fund_reasons:
            for r in fund_reasons:
                st.markdown(f"- {r}")
        else:
            st.write("暫無詳細財務數據。")

    st.markdown("---")
    st.subheader("🔮 未來走勢預測")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("#### 🗓️ **未來一週 (短期)**")
        st.info(pred_week)
    with p2:
        st.markdown("#### 🗓️ **未來一個月 (中期)**")
        st.info(pred_month)

    # 7. 圖表繪製
    st.markdown("---")
    st.subheader("📉 技術與籌碼圖表分析")
    df_chart = df.tail(120)

    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=('K線與均線 (MA5/20/60)', '成交量 (Vol)', 'KDJ 指標 (9,3,3)', 'MACD 指標')
    )

    # 1. K線
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], 
        low=df_chart['Low'], close=df_chart['Close'], name='K線',
        increasing_line_color='red', decreasing_line_color='green'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA20'], line=dict(color='blue', width=1.5), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA60'], line=dict(color='purple', width=2), name='MA60'), row=1, col=1)

    # 2. 成交量
    colors_vol = ['red' if c >= o else 'green' for c, o in zip(df_chart['Close'], df_chart['Open'])]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors_vol, name='成交量'), row=2, col=1)

    # 3. KDJ 指標
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['K'], line=dict(color='blue', width=1.2), name='K值'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['D'], line=dict(color='orange', width=1.2), name='D值'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['J'], line=dict(color='purple', width=1, dash='dot'), name='J值'), row=3, col=1)
    
    fig.add_hline(y=80, line_width=1, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=20, line_width=1, line_dash="dash", line_color="green", row=3, col=1)

    # 4. MACD
    colors_macd = ['red' if h >= 0 else 'green' for h in df_chart['MACD_Hist']]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], marker_color=colors_macd, name='MACD柱狀體'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['DIF'], line=dict(color='blue', width=1.2), name='DIF'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD_Signal'], line=dict(color='orange', width=1.2), name='Signal'), row=4, col=1)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=850,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    st.caption("免責聲明：本 App 分析結果皆由技術與財務邏輯自動推導，僅供參考，不代表任何投資建議。")
