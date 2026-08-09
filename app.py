import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as bg
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# 設定網頁標題與版面布局
st.set_page_config(
    page_title="台股全方位分析儀表板", page_layout="wide", initial_sidebar_state="expanded"
)

st.title("📈 台股技術面與趨勢分析系統")
st.caption("自動判斷多空趨勢、動能來源及未來走勢預測")

# 側邊欄輸入
st.sidebar.header("股票設定")
stock_id = st.sidebar.text_input(
    "請輸入台股代號（例如：2330 或 2317）", value="2330"
)
market_type = st.sidebar.radio("市場類型", ["上市 (.TW)", "上櫃 (.TWO)"])

# 處理台股代號格式
suffix = ".TW" if "上市" in market_type else ".TWO"
ticker_symbol = f"{stock_id.strip()}{suffix}"


@st.cache_data(ttl=3600)
def load_data(symbol):
    """抓取近兩年的股票數據"""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=730)
    df = yf.download(symbol, start=start_date, end=end_date)

    if df.empty:
        return None

    # 清理多層索引 (yfinance 在新版本有時會回傳 MultiIndex)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 計算技術指標
    df["MA5"] = df["Close"].rolling(window=5).mean()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA60"] = df["Close"].rolling(window=60).mean()
    df["Vol_MA5"] = df["Volume"].rolling(window=5).mean()

    # 計算 RSI (14日)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df


df = load_data(ticker_symbol)

if df is None or len(df) < 60:
    st.error("查無此股票數據，請確認股票代號或市場類型是否正確！")
else:
    # 獲取最新資料與歷史數值
    latest = df.iloc[-1]
    prev_close = df.iloc[-2]["Close"]
    close_price = latest["Close"]
    price_change = close_price - prev_close
    pct_change = (price_change / prev_close) * 100

    ma5, ma20, ma60 = latest["MA5"], latest["MA20"], latest["MA60"]
    rsi = latest["RSI"]
    vol_ratio = (
        latest["Volume"] / latest["Vol_MA5"] if latest["Vol_MA5"] > 0 else 1.0
    )

    # 1. 關鍵指標展示
    st.subheader(f"📊 {ticker_symbol} 當前市場概況")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新收盤價", f"{close_price:.2f} 元", f"{pct_change:+.2f}%")
    col2.metric("5日均線 (MA5)", f"{ma5:.2f}")
    col3.metric("20日月線 (MA20)", f"{ma20:.2f}")
    col4.metric("相對強弱指標 (RSI14)", f"{rsi:.1f}")

    # 2. 趨勢與現況判斷邏輯
    if close_price > ma5 > ma20 > ma60:
        status = "強勢上升趨勢 🚀"
        status_color = "red"  # 台股習慣：紅漲綠跌
        status_desc = (
            "股價位於所有短中長期均線之上，且均線呈現多頭排列，整體走勢強勁。"
        )
    elif close_price < ma5 < ma20 < ma60:
        status = "明確下跌趨勢 📉"
        status_color = "green"
        status_desc = (
            "股價受壓於所有均線之下，均線呈空頭排列，下行風險較高。"
        )
    else:
        status = "盤整震盪階段 ⚖️"
        status_color = "orange"
        status_desc = "股價在均線附近交織或於一定區間內游走，方向尚未完全明朗。"

    # 3. 動能來源分析
    momentum_reasons = []
    if vol_ratio >= 1.5:
        momentum_reasons.append(
            f"**成交量爆發**：當日成交量為 5 日均量的 {vol_ratio:.1f} 倍，顯示資金大幅進駐或換手。"
        )
    elif vol_ratio <= 0.6:
        momentum_reasons.append(
            "**量縮整理**：成交量顯著萎縮，市場觀望氣氛濃厚，可能在等待突破方向。"
        )

    if rsi >= 70:
        momentum_reasons.append(
            f"**買盤極度強勁 (RSI: {rsi:.1f})**：進入超買區，短期多頭佔據絕對優勢，但需留意獲利了結賣壓。"
        )
    elif rsi <= 30:
        momentum_reasons.append(
            f"**賣壓過度宣洩 (RSI: {rsi:.1f})**：進入超賣區，短期可能存在技術性彈升空間。"
        )

    if close_price > ma20 and ma5 > ma20:
        momentum_reasons.append(
            "**短線多頭控盤**：股價站在月線之上且短天期均線向上發散，提供股價支撐。"
        )
    elif close_price < ma20 and ma5 < ma20:
        momentum_reasons.append(
            "**空頭力道壓制**：股價跌破月線且短天期均線向下，下方支撐需尋求更長期的均線。"
        )

    if not momentum_reasons:
        momentum_reasons.append(
            "目前市場動能較為平淡，股價主要受大盤與產業消息面拉扯。"
        )

    # 4. 未來走勢預測邏輯
    # 短期（1週）
    if "上升" in status:
        pred_week = "預計延續震盪偏多走勢。若能持續站穩 MA5，將有機會再創高；但若跌破 MA5，可能面臨短線拉回尋找 MA20 支撐。"
    elif "下跌" in status:
        pred_week = "預計探底或弱勢震盪。在未能站回 MA5 前，不宜盲目抄底，仍需防範續跌風險。"
    else:
        pred_week = "預計維持區間整理。需密切關注是否能放量突破區間上緣或跌破區間下緣來決定短線方向。"

    # 中期（1個月）
    if close_price > ma60:
        pred_month = "中線格局偏多。季線（MA60）趨勢向上提供強勁支撐，只要季線不破，中長期震盪向上趨勢未變。"
    else:
        pred_month = "中線受壓明顯。季線（MA60）在上方形成壓力蓋頂，需要時間整理消化套牢籌碼，才能築底反彈。"

    # --- 呈現分析結果卡片 ---
    st.markdown("---")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("📌 股票當前現況")
        st.markdown(
            f"### **狀態：:{status_color}[{status}]**"
        )
        st.write(status_desc)

        st.subheader("⚡ 動能來源分析")
        for reason in momentum_reasons:
            st.markdown(f"- {reason}")

    with col_b:
        st.subheader("🔮 走勢預測（技術面推論）")
        st.markdown("#### 🗓️ **未來一週 (短期)**")
        st.info(pred_week)

        st.markdown("#### 🗓️ **未來一個月 (中期)**")
        st.info(pred_month)

    # 5. 繪製 K 線圖與技術指標圖表
    st.markdown("---")
    st.subheader("📉 技術分析圖表 (近半年)")

    df_chart = df.tail(120)  # 取近 120 個交易日呈現

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
        subplot_titles=("K線與均線", "成交量"),
    )

    # K線圖
    fig.add_trace(
        go.Candlestick(
            x=df_chart.index,
            open=df_chart["Open"],
            high=df_chart["High"],
            low=df_chart["Low"],
            close=df_chart["Close"],
            name="K線",
            increasing_line_color="red",
            decreasing_line_color="green",
        ),
        row=1,
        col=1,
    )

    # 均線
    fig.add_trace(
        go.Scatter(
            x=df_chart.index,
            y=df_chart["MA5"],
            line=dict(color="orange", width=1),
            name="MA5",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df_chart.index,
            y=df_chart["MA20"],
            line=dict(color="blue", width=1.5),
            name="MA20",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df_chart.index,
            y=df_chart["MA60"],
            line=dict(color="purple", width=2),
            name="MA60",
        ),
        row=1,
        col=1,
    )

    # 成交量柱狀圖
    colors = [
        "red" if c >= o else "green"
        for c, o in zip(df_chart["Close"], df_chart["Open"])
    ]
    fig.add_trace(
        go.Bar(
            x=df_chart.index,
            y=df_chart["Volume"],
            marker_color=colors,
            name="成交量",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption("免責聲明：本 App 之分析結果皆由技術指標邏輯自動推導，僅供參考，不代表任何投資建議。")
