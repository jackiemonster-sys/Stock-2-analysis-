import datetime
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

# 1. 頁面設定
st.set_page_config(page_title="台股三合一全方位分析 (證交所/櫃買官方源)", layout="wide")

st.title("📈 台股全方位分析系統 (證交所/櫃買官方資料源)")
st.caption("直接對接臺灣證券交易所與櫃買中心官方數據，進行技術面與籌碼面分析")

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 2. 取得上市櫃股票清單 (證交所 Open Data)
@st.cache_data(ttl=86400)
def get_taiwan_stock_list():
    options = []
    stock_map = {}
    
    # 預設熱門選單 (作為預備機制)
    default_options = [
        "2330 台積電 (上市)", "2317 鴻海 (上市)", "2408 南亞科 (上市)",
        "2454 聯發科 (上市)", "2382 廣達 (上市)", "8069 元太 (上櫃)"
    ]
    default_map = {
        "2330 台積電 (上市)": {"stock_id": "2330", "stock_name": "台積電", "market_type": "上市"},
        "2317 鴻海 (上市)": {"stock_id": "2317", "stock_name": "鴻海", "market_type": "上市"},
        "2408 南亞科 (上市)": {"stock_id": "2408", "stock_name": "南亞科", "market_type": "上市"},
        "2454 聯發科 (上市)": {"stock_id": "2454", "stock_name": "聯發科", "market_type": "上市"},
        "2382 廣達 (上市)": {"stock_id": "2382", "stock_name": "廣達", "market_type": "上市"},
        "8069 元太 (上櫃)": {"stock_id": "8069", "stock_name": "元太", "market_type": "上櫃"}
    }

    try:
        # 上市股票
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url_twse, headers=HTTP_HEADERS, timeout=6)
        if res.status_code == 200:
            for item in res.json():
                sid = item.get("Code", "").strip()
                sname = item.get("Name", "").strip()
                if sid and len(sid) == 4 and sid.isdigit():
                    label = f"{sid} {sname} (上市)"
                    options.append(label)
                    stock_map[label] = {"stock_id": sid, "stock_name": sname, "market_type": "上市"}
                    
        # 上櫃股票
        url_tpex = "https://www.tpex.org.tw/openapi/v1/mopsrev_result"
        res_tpex = requests.get(url_tpex, headers=HTTP_HEADERS, timeout=6)
        if res_tpex.status_code == 200:
            for item in res_tpex.json():
                sid = item.get("CompanyCode", "").strip()
                sname = item.get("CompanyName", "").strip()
                if sid and len(sid) == 4 and sid.isdigit():
                    label = f"{sid} {sname} (上櫃)"
                    if label not in stock_map:
                        options.append(label)
                        stock_map[label] = {"stock_id": sid, "stock_name": sname, "market_type": "上櫃"}
    except Exception:
        pass

    if not options:
        return default_options, default_map
    return options, stock_map

stock_options, stock_map = get_taiwan_stock_list()

# 查詢介面
st.markdown("### 🔍 股票查詢")
selected_stock_label = st.selectbox(
    "輸入股票代號或中文名稱進行搜尋",
    options=stock_options,
    index=0
)

selected_info = stock_map[selected_stock_label]
stock_id = selected_info["stock_id"]
stock_name = selected_info["stock_name"]
market_type = selected_info["market_type"]

# 3. 抓取證交所 / 櫃買中心歷史 K 線資料
@st.cache_data(ttl=3600)
def fetch_twse_tpex_kline(stock_id, market_type):
    today = datetime.date.today()
    all_data = []

    # 抓取最近 6 個月的月份數據
    for i in range(6):
        target_date = today - datetime.timedelta(days=i*28)
        date_str = target_date.strftime("%Y%m01")

        try:
            if market_type == "上市":
                url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={stock_id}"
                res = requests.get(url, headers=HTTP_HEADERS, timeout=5)
                data = res.json()
                if data.get("stat") == "OK" and "data" in data:
                    all_data.extend(data["data"])
            else:
                # 上櫃 (TPEx 西元轉民國年格式)
                roc_year = target_date.year - 1911
                roc_date_str = f"{roc_year}/{target_date.strftime('%m')}"
                url = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={roc_date_str}&stkno={stock_id}"
                res = requests.get(url, headers=HTTP_HEADERS, timeout=5)
                data = res.json()
                if "aaData" in data:
                    all_data.extend(data["aaData"])
        except Exception:
            continue

    if not all_data:
        return None

    # 解析與整理成 DataFrame
    parsed_rows = []
    for row in all_data:
        try:
            # 日期轉西元 (例: 112/05/02 -> 2023-05-02)
            raw_date = row[0].replace(" ", "")
            parts = raw_date.split("/")
            year = int(parts[0]) + 1911
            date_fmt = f"{year}-{parts[1]:>02}-{parts[2]:>02}"

            # 解析開高低收與成交量 (移除逗號)
            vol = float(row[1].replace(",", ""))
            open_p = float(row[3].replace(",", ""))
            high_p = float(row[4].replace(",", ""))
            low_p = float(row[5].replace(",", ""))
            close_p = float(row[6].replace(",", ""))

            parsed_rows.append({
                "date": pd.to_datetime(date_fmt),
                "Open": open_p,
                "High": high_p,
                "Low": low_p,
                "Close": close_p,
                "Volume": vol
            })
        except Exception:
            continue

    if not parsed_rows:
        return None

    df = pd.DataFrame(parsed_rows)
    df = df.drop_duplicates(subset=['date']).sort_values('date').set_index('date')
    return df

# 計算技術指標
def calculate_indicators(df):
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()

    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp1 - exp2
    df['MACD_Signal'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['DIF'] - df['MACD_Signal']

    # KDJ
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    rsv = (df['Close'] - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)

    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']

    # OBV
    df['OBV'] = ((df['Close'].diff() > 0).astype(int) * 2 - 1) * df['Volume']
    df['OBV'] = df['OBV'].fillna(0).cumsum()
    df['OBV_MA10'] = df['OBV'].rolling(window=10).mean()

    return df

with st.spinner("正在直接向台灣證券交易所/櫃買中心讀取數據..."):
    df = fetch_twse_tpex_kline(stock_id, market_type)

if df is None or len(df) < 10:
    st.error("⚠️ 證交所 API 暫無回應或查無此股票，請稍後重試！")
else:
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev_latest = df.iloc[-2]

    prev_close = float(prev_latest['Close'])
    close_price = float(latest['Close'])
    price_change = close_price - prev_close
    pct_change = (price_change / prev_close) * 100
    trade_date = df.index[-1].strftime("%Y/%m/%d")

    st.markdown("---")
    st.subheader(f"📊 {stock_name} ({stock_id}) 核心行情")
    st.markdown(f"🗓️ **最新交易日：`{trade_date}`** ｜ 🏛️ **市場類別：`{market_type}`**")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("最新收盤價", f"{close_price:.2f} 元", f"{pct_change:+.2f}%")
    c2.metric("最高價", f"{latest['High']:.2f} 元")
    c3.metric("最低價", f"{latest['Low']:.2f} 元")
    c4.metric("成交量", f"{int(latest['Volume']/1000):,} 張")

    # 技術面狀態判斷
    ma5, ma20, ma60 = float(latest['MA5']), float(latest['MA20']), float(latest['MA60'])
    if close_price > ma5 > ma20:
        tech_status, color = "多頭排列 🚀", "red"
        tech_desc = "短中期均線呈多頭排列，站穩 MA5 / MA20 之上。"
    elif close_price < ma5 < ma20:
        tech_status, color = "空頭整理 📉", "green"
        tech_desc = "股價落於短期均線之下，宜防範短線下行修正。"
    else:
        tech_status, color = "高低震盪 ⚖️", "orange"
        tech_desc = "均線糾結，方向性尚在醞釀中。"

    # 顯示分析
    st.markdown("---")
    st.subheader("📌 技術分析總覽")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"#### 📈 **現況狀態**：:{color}[{tech_status}]")
        st.write(tech_desc)
    with col2:
        st.markdown("#### 🔍 **關鍵指標數據**")
        st.markdown(f"- **MA5**：{ma5:.2f} ｜ **MA20**：{ma20:.2f}")
        st.markdown(f"- **KDJ (9,3,3)**：K = {latest['K']:.1f}, D = {latest['D']:.1f}")
        st.markdown(f"- **MACD 柱狀體**：{latest['MACD_Hist']:+.2f}")

    # K線圖表
    st.markdown("---")
    st.subheader("📉 K線與指標繪製")
    df_chart = df.tail(80)

    fig = make_subplots(
        rows=3, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03, 
        row_heights=[0.5, 0.25, 0.25],
        subplot_titles=('K線與均線', 'KDJ 指標', 'MACD 指標')
    )

    # 1. K線
    fig.add_trace(go.Candlestick(
        x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], 
        low=df_chart['Low'], close=df_chart['Close'], name='K線',
        increasing_line_color='red', decreasing_line_color='green'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['MA20'], line=dict(color='blue', width=1.5), name='MA20'), row=1, col=1)

    # 2. KDJ
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['K'], line=dict(color='blue', width=1.2), name='K值'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['D'], line=dict(color='orange', width=1.2), name='D值'), row=2, col=1)

    # 3. MACD
    colors_macd = ['red' if h >= 0 else 'green' for h in df_chart['MACD_Hist']]
    fig.add_trace(go.Bar(x=df_chart.index, y=df_chart['MACD_Hist'], marker_color=colors_macd, name='MACD柱狀體'), row=3, col=1)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=600,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)
