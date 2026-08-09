import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st
import yfinance as yf

# 1. 頁面設定
st.set_page_config(page_title="台股三合一全方位分析", layout="wide")

st.title("📈 台股全方位分析系統 (籌碼強化版)")
st.caption("結合技術面 (均線/MACD)、深度籌碼面 (三大法人/動能集中度) 與基本面的智慧評估")

# 2. 主頁面查詢區塊
st.markdown("### 🔍 股票查詢")
col_input1, col_input2 = st.columns([2, 1])

with col_input1:
    stock_id = st.text_input("請輸入台股代號", value="2330", help="例如：2330 或 2317").strip()

with col_input2:
    market_type = st.selectbox("市場類型", ["上市 (.TW)", "上櫃 (.TWO)"])

suffix = ".TW" if "上市" in market_type else ".TWO"
ticker_symbol = f"{stock_id}{suffix}"

# 抓取 FinMind 三大法人資料 (若失敗則自動退回技術面籌碼估算)
@st.cache_data(ttl=3600)
def fetch_institutional_data(stock_id):
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        parameter = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date
        }
        res = requests.get(url, params=parameter, timeout=5)
        data = res.json()
        if data.get("status") == 200 and data.get("data"):
            df_inst = pd.DataFrame(data["data"])
            # 統計近 5 日三大法人買賣總張數
            df_inst['buy_sell'] = (df_inst['buy'] - df_inst['sell']) / 1000 # 轉為張數
            recent_df = df_inst.groupby('name')['buy_sell'].sum().round(0)
            return recent_df.to_dict()
    except Exception:
        pass
    return None

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
    
    # 籌碼面衍生指標 (OBV 與 價量流向)
    df['OBV'] = ((df['Close'].diff() > 0).astype(int) * 2 - 1) * df['Volume']
    df['OBV'] = df['OBV'].fillna(0).cumsum()
    df['OBV_MA10'] = df['OBV'].rolling(window=10).mean()

    info = ticker.info
    return df, info

df, info = load_stock_data(ticker_symbol)
inst_data = fetch_institutional_data(stock_id)

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
    st.subheader(f"📊 {ticker_symbol} 核心指標")
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

    # (B) 強化籌碼面評估
    chip_reasons = []
    chip_score = 0
    
    # B1: 法人籌碼 (真實數據)
    if inst_data:
        foreign = inst_data.get("Foreign_Investor", 0)
        investment_trust = inst_data.get("Investment_Trust", 0)
        dealer = inst_data.get("Dealer_Self", 0) + inst_data.get("Dealer_Hedging", 0)
        
        chip_reasons.append(f"**近 5 日外資買賣**：{foreign:+,.0f} 張")
        chip_reasons.append(f"**近 5 日投信買賣**：{investment_trust:+,.0f} 張")
        
        if foreign > 0 and investment_trust > 0:
            chip_reasons.append("🔥 **法人同買**：外資與投信聯手加碼，籌碼集中度極佳。")
            chip_score += 2
        elif foreign < 0 and investment_trust < 0:
            chip_reasons.append("⚠️ **法人同賣**：三大法人持續提款，籌碼面受壓。")
            chip_score -= 2
            
    # B2: 量價結構與 OBV (能量潮)
    obv_now = latest['OBV']
    obv_ma = latest['OBV_MA10']
    
    if obv_now > obv_ma:
        chip_reasons.append("**OBV 能量潮偏多**：資金持續淨流入，籌碼具備沉澱效益。")
        chip_score += 1
    else:
        chip_reasons.append("**OBV 能量潮偏空**：資金呈淨流出狀態，需注意換手停滯。")
        chip_score -= 1
        
    # B3: 爆量與窒息量判讀
    if vol_ratio >= 1.8 and price_change > 0:
        chip_reasons.append(f"**帶量突破**：成交量達到 5 日均量 {vol_ratio:.1f} 倍，主力強勢攻堅。")
        chip_score += 1
    elif vol_ratio >= 1.8 and price_change < 0:
        chip_reasons.append(f"**高檔/關鍵位爆量下跌**：成交量 {vol_ratio:.1f} 倍，恐有主力獲利出場賣壓。")
        chip_score -= 1
    elif vol_ratio <= 0.6:
        chip_reasons.append(f"**量能窒息**：成交量僅 5 日均量 {vol_ratio:.1f} 倍，籌碼沉澱進入觀望/洗盤階段。")

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
        pred_week = "技術面與籌碼面呈現強勢共振，短線站穩 MA5 有機會持續走揚。"
    elif "下跌" in tech_status or chip_score <= -2:
        pred_week = "籌碼面或技術面承壓，短線未見明確止跌訊號前宜謹慎觀望。"
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
        st.markdown("#### 💰 **籌碼面動態 (精細化)**")
        st.markdown(f"**狀態：{chip_status}**")
        st.markdown("**法人與籌碼流向：**")
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

    # 7. 圖表繪製 (加入 OBV 能量潮圖表)
    st.markdown("---")
    st.subheader("📉 技術與籌碼 (OBV) 圖表分析")
    df_chart = df.tail(120)

    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=('K線與均線 (MA5/20/60)', '成交量 (Vol)', 'OBV 能量潮 (籌碼動能)', 'MACD 指標')
    )

    # K線
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], 
        low=df_chart['Low'], close=df_chart['Close'], name='K線',
        increasing_line_color='red', decreasing_line_color='green'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA20'], line=dict(color='blue', width=1.5), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA60'], line=dict(color='purple', width=2), name='MA60'), row=1, col=1)

    # 成交量
    colors_vol = ['red' if c >= o else 'green' for c, o in zip(df_chart['Close'], df_chart['Open'])]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors_vol, name='成交量'), row=2, col=1)

    # OBV 能量潮
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['OBV'], line=dict(color='darkcyan', width=1.5), name='OBV'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['OBV_MA10'], line=dict(color='gray', width=1, dash='dot'), name='OBV 10MA'), row=3, col=1)

    # MACD
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
