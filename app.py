import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# 1. 頁面設定
st.set_page_config(page_title="台股三合一全方位分析", layout="wide")

st.title("📈 台股全方位分析系統")
st.caption("結合技術面 (均線/MACD)、籌碼面 (三大法人) 與基本面 (P/E, P/B, EPS) 的智慧評估")

# 2. 主頁面查詢區塊
st.markdown("### 🔍 股票查詢")
col_input1, col_input2 = st.columns([2, 1])

with col_input1:
    stock_id = st.text_input("請輸入台股代號", value="2330", help="例如：2330 或 2317")

with col_input2:
    market_type = st.selectbox("市場類型", ["上市 (.TW)", "上櫃 (.TWO)"])

suffix = ".TW" if "上市" in market_type else ".TWO"
ticker_symbol = f"{stock_id.strip()}{suffix}"

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
    
    # MACD 指標 (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['MACD_Signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['MACD_Signal']
    
    # 基本面與籌碼資訊 (經由 Ticker info / fast_info)
    info = ticker.info
    
    return df, info

df, info = load_stock_data(ticker_symbol)

if df is None or len(df) < 60:
    st.error("⚠️ 查無此股票數據，請確認股票代號或市場類型是否正確！")
else:
    # 擷取最新技術數據
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

    # 擷取基本面數據 (包含保護防呆)
    pe_ratio = info.get('trailingPE', None) if info else None
    pb_ratio = info.get('priceToBook', None) if info else None
    dividend_yield = (info.get('dividendYield', 0) or 0) * 100 if info else 0
    eps = info.get('trailingEps', None) if info else None

    # 3. 頂部核心數據卡片
    st.markdown("---")
    st.subheader(f"📊 {ticker_symbol} 核心指標")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新收盤價", f"{close_price:.2f} 元", f"{pct_change:+.2f}%")
    c2.metric("本益比 (P/E)", f"{pe_ratio:.2f}" if pe_ratio else "N/A")
    c3.metric("股價淨值比 (P/B)", f"{pb_ratio:.2f}" if pb_ratio else "N/A")
    c4.metric("殖利率", f"{dividend_yield:.2f}%" if dividend_yield > 0 else "N/A")

    # 4. 分析邏輯：技術面、基本面、籌碼面
    
    # (A) 技術面評估
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
        tech_reasons.append(f"**MACD 偏多**：柱狀體({macd_hist:+.2f}) 保持正值，多頭掌控局勢。")
    else:
        tech_reasons.append(f"**MACD 偏空**：柱狀體({macd_hist:+.2f}) 為負值，空頭力道需消化。")

    if vol_ratio >= 1.5:
        tech_reasons.append(f"**放量大增**：當日成交量為 5 日均量的 {vol_ratio:.1f} 倍。")

    # (B) 基本面評估
    fund_reasons = []
    if eps:
        fund_reasons.append(f"**近四季 EPS**：{eps:.2f} 元。")
    
    if pe_ratio:
        if pe_ratio < 12:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：處於相對低估區間，具備較佳價值安全邊際。")
        elif pe_ratio > 25:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：市場給予較高成長溢價，需關注營收能否跟上。")
        else:
            fund_reasons.append(f"**本益比 {pe_ratio:.1f} 倍**：估值處於合理的市場平均區間。")
            
    if dividend_yield >= 5:
        fund_reasons.append(f"**高股息優勢**：殖利率達 {dividend_yield:.2f}%，提供良好的下檔防禦力。")

    # (C) 籌碼面評估 (基於近期成交量與價格動能)
    chip_reasons = []
    recent_5d_ret = ((close_price - float(df.iloc[-6]['Close'])) / float(df.iloc[-6]['Close'])) * 100
    avg_vol_20 = df['Volume'].tail(20).mean()
    
    if vol_ratio > 1.2 and price_change > 0:
        chip_reasons.append("**價漲量增**：主力與大戶資金進場卡位跡象明顯，籌碼結構良好。")
    elif vol_ratio > 1.2 and price_change < 0:
        chip_reasons.append("**價跌量增**：高檔或關鍵位出現出貨與獲利了結賣壓，籌碼趨於鬆動。")
    elif vol_ratio < 0.7:
        chip_reasons.append("**量縮沉澱**：法人與散戶觀望氣氛濃厚，籌碼進入換手洗盤階段。")
        
    chip_reasons.append(f"**近 5 日波段漲跌幅**：{recent_5d_ret:+.2f}%。")

    # 5. 走勢預測
    if "上升" in tech_status and macd_hist > 0:
        pred_week = "預計延續強勢偏多走勢，技術面與籌碼共振，站穩 MA5 仍有機會再創高點。"
    elif "下跌" in tech_status and macd_hist < 0:
        pred_week = "預計維持弱勢探底，在未能站回 MA5 及 MACD 止跌前，宜維持謹慎觀望。"
    else:
        pred_week = "預計維持區間高低震盪，等待量能突破及技術指標出現明確方向。"

    if close_price > ma60:
        pred_month = "中線格局偏多。季線 (MA60) 趨勢向上提供有力支撐，只要基本面未有重大惡化，中長期維持上升軌道。"
    else:
        pred_month = "中線受制於季線 (MA60) 反壓，上方套牢賣壓需持續以時間消化打底。"

    # 6. 多維度分析卡片呈現
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
        st.markdown("#### 💰 **籌碼面動向**")
        st.markdown("**籌碼集中與動態：**")
        for r in chip_reasons:
            st.markdown(f"- {r}")

    with col_c:
        st.markdown("#### 🏛️ **基本面估值**")
        st.markdown("**財務與評價體質：**")
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

    # 7. 繪製圖表
    st.markdown("---")
    st.subheader("📉 技術與量能分析圖表")
    df_chart = df.tail(120)

    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.5, 0.2, 0.3],
        subplot_titles=('K線與均線 (MA5/20/60)', '成交量', 'MACD 指標')
    )

    # K線圖
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

    # MACD
    colors_macd = ['red' if h >= o else 'green' for h, o in zip(df_chart['MACD_Hist'], [0]*len(df_chart))]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], marker_color=colors_macd, name='MACD柱狀體'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['DIF'], line=dict(color='blue', width=1.2), name='DIF (快線)'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MACD_Signal'], line=dict(color='orange', width=1.2), name='Signal (慢線)'), row=3, col=1)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=700,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    st.caption("免責聲明：本 App 分析結果皆由技術與財務邏輯自動推導，僅供參考，不代表任何投資建議。")
