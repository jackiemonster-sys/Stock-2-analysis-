import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# 必須放在程式碼的第一行 Streamlit 指令
st.set_page_config(page_title="台股分析", layout="wide")

st.title("📈 台股技術面與趨勢分析系統")
st.caption("自動判斷多空趨勢、動能來源及未來走勢預測")

# 側邊欄設定
st.sidebar.header("股票設定")
stock_id = st.sidebar.text_input("請輸入台股代號（例如：2330 或 2317）", value="2330")
market_type = st.sidebar.radio("市場類型", ["上市 (.TW)", "上櫃 (.TWO)"])

suffix = ".TW" if "上市" in market_type else ".TWO"
ticker_symbol = f"{stock_id.strip()}{suffix}"

@st.cache_data(ttl=3600)
def load_data(symbol):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    
    # 抓取數據
    df = yf.download(symbol, start=start_date, end=end_date, progress=False)
    
    if df.empty:
        return None
        
    # 清理 MultiIndex 欄位名稱
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # 技術指標計算
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['Vol_MA5'] = df['Volume'].rolling(window=5).mean()
    
    # RSI 計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    return df

df = load_data(ticker_symbol)

if df is None or len(df) < 60:
    st.error("查無此股票數據，請確認股票代號或市場類型是否正確！")
else:
    # 擷取數值
    latest = df.iloc[-1]
    prev_close = float(df.iloc[-2]['Close'])
    close_price = float(latest['Close'])
    price_change = close_price - prev_close
    pct_change = (price_change / prev_close) * 100
    
    ma5 = float(latest['MA5'])
    ma20 = float(latest['MA20'])
    ma60 = float(latest['MA60'])
    rsi = float(latest['RSI'])
    vol_ratio = float(latest['Volume'] / latest['Vol_MA5']) if latest['Vol_MA5'] > 0 else 1.0

    # 1. 指標卡片
    st.subheader(f"📊 {ticker_symbol} 當前市場概況")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新收盤價", f"{close_price:.2f} 元", f"{pct_change:+.2f}%")
    c2.metric("5日均線 (MA5)", f"{ma5:.2f}")
    c3.metric("20日月線 (MA20)", f"{ma20:.2f}")
    c4.metric("相對強弱 (RSI14)", f"{rsi:.1f}")

    # 2. 狀態與動能判斷
    if close_price > ma5 > ma20 > ma60:
        status, color = "強勢上升趨勢 🚀", "red"
        status_desc = "股價位於所有均線之上，呈多頭排列，走勢強勁。"
    elif close_price < ma5 < ma20 < ma60:
        status, color = "明確下跌趨勢 📉", "green"
        status_desc = "股價受壓於所有均線之下，呈空頭排列，風險較高。"
    else:
        status, color = "盤整震盪階段 ⚖️", "orange"
        status_desc = "股價於均線附近交織，方向尚未明確。"

    momentum_reasons = []
    if vol_ratio >= 1.5:
        momentum_reasons.append(f"**成交量爆發**：成交量為 5 日均量的 {vol_ratio:.1f} 倍，資金顯著進駐。")
    elif vol_ratio <= 0.6:
        momentum_reasons.append("**量縮整理**：成交量萎縮，市場觀望氣氛濃。")

    if rsi >= 70:
        momentum_reasons.append(f"**超買區 (RSI: {rsi:.1f})**：多頭強勁，但需留意獲利了結賣壓。")
    elif rsi <= 30:
        momentum_reasons.append(f"**超賣區 (RSI: {rsi:.1f})**：賣壓宣洩，短線可能迎來技術性反彈。")

    if close_price > ma20 and ma5 > ma20:
        momentum_reasons.append("**短線多頭控盤**：股價站在月線之上，短線具備支撐。")
    elif close_price < ma20 and ma5 < ma20:
        momentum_reasons.append("**空頭力道壓制**：跌破月線，下尋長期均線支撐。")

    if not momentum_reasons:
        momentum_reasons.append("動能平淡，主要隨大盤與消息面波動。")

    # 3. 走勢預測
    pred_week = "預計延續偏多走勢，站穩 MA5 仍有高點可期。" if "上升" in status else ("弱勢探底，尚未站回 MA5 前不宜貿然抄底。" if "下跌" in status else "維持區間震盪，等待量能突破方向。")
    pred_month = "中線偏多，季線（MA60）向上提供有力支撐。" if close_price > ma60 else "中線受壓，季線形成上方壓力，需要時間築底。"

    # 4. 畫面呈現
    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("📌 股票現況")
        st.markdown(f"### 狀態：:{color}[{status}]")
        st.write(status_desc)
        st.subheader("⚡ 動能來源")
        for r in momentum_reasons:
            st.markdown(f"- {r}")

    with col_b:
        st.subheader("🔮 走勢預測")
        st.markdown("#### 🗓️ **未來一週**")
        st.info(pred_week)
        st.markdown("#### 🗓️ **未來一個月**")
        st.info(pred_month)

    # 5. K 線圖表
    st.markdown("---")
    st.subheader("📉 技術分析圖表 (近半年)")
    df_chart = df.tail(120)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3], subplot_titles=('K線與均線', '成交量'))
    fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='K線', increasing_line_color='red', decreasing_line_color='green'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA20'], line=dict(color='blue', width=1.5), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA60'], line=dict(color='purple', width=2), name='MA60'), row=1, col=1)
    
    colors = ['red' if c >= o else 'green' for c, o in zip(df_chart['Close'], df_chart['Open'])]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors, name='成交量'), row=2, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False, height=550, margin=dict(l=10, r=10, t=30, b=10))
    
    st.plotly_chart(fig, use_container_width=True)
    st.caption("免責聲明：本 App 分析結果僅供參考，不代表任何投資建議。")
