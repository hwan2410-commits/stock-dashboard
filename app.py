import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timezone, timedelta
import yfinance as yf
import FinanceDataReader as fdr
from modules.korean_stocks import get_market_movers, get_stock_detail, get_ticker_name
from modules.us_stocks import get_us_movers, get_stock_history
from modules.recommender import get_kr_recommendations, get_us_recommendations, compute_signals
from modules.news_fetcher import fetch_news

st.set_page_config(
    page_title="글로벌 주식 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .big-metric { font-size: 1.4rem; font-weight: bold; }
    .up { color: #FF4B4B; }
    .down { color: #1E88E5; }
    .section-header {
        background: linear-gradient(90deg, #1a1a2e, #16213e);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        margin: 20px 0 10px 0;
        font-size: 1.2rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.title("📈 글로벌 주식 대시보드")
    st.caption(f"업데이트: {datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')} KST")
    st.divider()

    menu = st.radio(
        "메뉴",
        ["🏠 홈 / 시장 요약", "🇰🇷 한국 주식", "🇺🇸 미국 주식", "💡 매매 추천", "📰 주요 뉴스"],
        label_visibility="collapsed",
    )

    st.divider()
    top_n = st.slider("TOP 종목 수", 5, 20, 10)
    if st.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ── 캐시된 데이터 로딩 ────────────────────────────────────
@st.cache_data(ttl=600)
def load_kospi_movers(n):
    return get_market_movers("KOSPI", n)

@st.cache_data(ttl=600)
def load_kosdaq_movers(n):
    return get_market_movers("KOSDAQ", n)

@st.cache_data(ttl=600)
def load_us_movers(n):
    return get_us_movers(n)

@st.cache_data(ttl=1800)
def load_news():
    return fetch_news(5)

@st.cache_data(ttl=300)
def load_kr_chart(ticker, days):
    return get_stock_detail(ticker, days)

@st.cache_data(ttl=3600)
def load_us_chart(ticker, period):
    return get_stock_history(ticker, period)

@st.cache_data(ttl=1800)
def load_kr_recommendations(tickers: tuple, names: tuple):
    return get_kr_recommendations(list(tickers), dict(names))

@st.cache_data(ttl=1800)
def load_us_recommendations(watch: tuple):
    return get_us_recommendations(list(watch))


def render_movers_table(gainers: pd.DataFrame, losers: pd.DataFrame, col_price="종가", col_change="등락률"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔴 상승 TOP")
        if gainers.empty:
            st.info("데이터를 불러오는 중...")
        else:
            st.dataframe(gainers, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("#### 🔵 하락 TOP")
        if losers.empty:
            st.info("데이터를 불러오는 중...")
        else:
            st.dataframe(losers, use_container_width=True, hide_index=True)


def render_candlestick(df: pd.DataFrame, title: str):
    if df is None or df.empty:
        st.warning("차트 데이터 없음")
        return

    open_col = "시가" if "시가" in df.columns else "Open"
    high_col = "고가" if "고가" in df.columns else "High"
    low_col  = "저가" if "저가" in df.columns else "Low"
    close_col = "종가" if "종가" in df.columns else "Close"

    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df[open_col],
        high=df[high_col],
        low=df[low_col],
        close=df[close_col],
        increasing_line_color="#FF4B4B",
        decreasing_line_color="#1E88E5",
    )])
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════
# 홈 / 시장 요약
# ══════════════════════════════════════════════════════════
if menu == "🏠 홈 / 시장 요약":
    st.title("🌐 글로벌 주식 시장 요약")

    with st.spinner("시장 데이터 로딩 중..."):
        kospi_g, kospi_l = load_kospi_movers(5)
        us_g, us_l = load_us_movers(5)

    # 지수 현황
    st.markdown('<div class="section-header">📊 주요 지수</div>', unsafe_allow_html=True)
    indices = {
        "KOSPI": "^KS11",
        "KOSDAQ": "^KQ11",
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
    }
    cols = st.columns(5)
    for i, (name, ticker) in enumerate(indices.items()):
        try:
            info = yf.download(ticker, period="2d", auto_adjust=True, progress=False)
            # yfinance MultiIndex 처리
            close = info["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            if len(close) >= 2:
                prev = float(close.iloc[-2])
                curr = float(close.iloc[-1])
                chg = (curr - prev) / prev * 100
                arrow = "▲" if chg >= 0 else "▼"
                cols[i].metric(
                    name,
                    f"{curr:,.2f}",
                    f"{arrow} {abs(chg):.2f}%",
                )
        except:
            cols[i].metric(name, "로딩 중", "")

    st.divider()

    st.markdown('<div class="section-header">🇰🇷 KOSPI 상위 등락</div>', unsafe_allow_html=True)
    render_movers_table(kospi_g, kospi_l)

    st.markdown('<div class="section-header">🇺🇸 미국 주식 상위 등락</div>', unsafe_allow_html=True)
    render_movers_table(us_g, us_l, col_price="현재가", col_change="등락률")


# ══════════════════════════════════════════════════════════
# 한국 주식
# ══════════════════════════════════════════════════════════
elif menu == "🇰🇷 한국 주식":
    st.title("🇰🇷 한국 주식")

    tab1, tab2, tab3 = st.tabs(["KOSPI", "KOSDAQ", "종목 차트"])

    with tab1:
        st.markdown("#### KOSPI 상승/하락 TOP")
        with st.spinner("KOSPI 데이터 로딩 중..."):
            g, l = load_kospi_movers(top_n)
        render_movers_table(g, l)

    with tab2:
        st.markdown("#### KOSDAQ 상승/하락 TOP")
        with st.spinner("KOSDAQ 데이터 로딩 중..."):
            g, l = load_kosdaq_movers(top_n)
        render_movers_table(g, l)

    with tab3:
        st.markdown("#### 종목 차트 조회")
        c1, c2 = st.columns([3, 1])
        ticker_input = c1.text_input("종목 코드 입력 (예: 005930 = 삼성전자)", "005930")
        period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365, "2년": 730}
        period_label = c2.selectbox("기간", list(period_map.keys()), index=1)
        if ticker_input:
            with st.spinner("차트 로딩 중..."):
                df = load_kr_chart(ticker_input, period_map[period_label])
            name = get_ticker_name(ticker_input)
            render_candlestick(df, f"{name} ({ticker_input}) 캔들차트")

            if not df.empty:
                sig = compute_signals(df)
                if sig:
                    st.markdown("**기술적 분석 신호**")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("매매 신호", sig["신호"])
                    col2.metric("RSI", sig["RSI"])
                    col3.metric("현재가", f"{sig['현재가']:,}")
                    col4.metric("20일 이평선", f"{sig['20일선']:,}")
                    st.info(f"근거: {sig['이유']}")


# ══════════════════════════════════════════════════════════
# 미국 주식
# ══════════════════════════════════════════════════════════
elif menu == "🇺🇸 미국 주식":
    st.title("🇺🇸 미국 주식")

    tab1, tab2 = st.tabs(["상승/하락 TOP", "종목 차트"])

    with tab1:
        with st.spinner("미국 주식 데이터 로딩 중..."):
            g, l = load_us_movers(top_n)
        render_movers_table(g, l, col_price="현재가", col_change="등락률")

    with tab2:
        st.markdown("#### 종목 차트 조회")
        c1, c2 = st.columns([2, 1])
        us_ticker = c1.text_input("티커 입력 (예: AAPL, TSLA, NVDA)", "AAPL")
        period = c2.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], index=1)

        if us_ticker:
            with st.spinner("차트 로딩 중..."):
                df = load_us_chart(us_ticker.upper(), period)
            render_candlestick(df, f"{us_ticker.upper()} 캔들차트")

            if not df.empty:
                sig = compute_signals(df)
                if sig:
                    st.markdown("**기술적 분석 신호**")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("매매 신호", sig["신호"])
                    col2.metric("RSI", sig["RSI"])
                    col3.metric("현재가", f"${sig['현재가']:.2f}")
                    col4.metric("20일 이평선", f"${sig['20일선']:.2f}")
                    st.info(f"근거: {sig['이유']}")


# ══════════════════════════════════════════════════════════
# 매매 추천
# ══════════════════════════════════════════════════════════
elif menu == "💡 매매 추천":
    st.title("💡 오늘의 매매 추천 종목")
    st.caption("RSI, MACD, 이동평균선 기반 기술적 분석 결과입니다. 투자 판단의 참고 자료로만 활용하세요.")

    tab1, tab2 = st.tabs(["🇰🇷 한국 추천", "🇺🇸 미국 추천"])

    with tab1:
        with st.spinner("한국 주식 분석 중... (캐시 없을 시 30~60초 소요)"):
            try:
                listing = fdr.StockListing("KOSPI")
                listing = listing[listing["Volume"] > 0]
                top_rows = listing.nlargest(20, "Volume")
                top_tickers = tuple(top_rows["Code"].tolist())
                names_tuple = tuple(zip(top_rows["Code"], top_rows["Name"]))
                rec_df = load_kr_recommendations(top_tickers, names_tuple)
                if rec_df.empty:
                    st.info("현재 매수 추천 기준을 충족하는 종목이 없습니다.")
                else:
                    st.dataframe(rec_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"데이터 로딩 오류: {e}")

    with tab2:
        with st.spinner("미국 주식 분석 중... (캐시 없을 시 20~30초 소요)"):
            watch = (
                "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                "AMD", "INTC", "NFLX", "PYPL", "UBER", "CRM", "ORCL", "ADBE",
                "COIN", "PLTR", "SOFI", "RIVN", "SHOP"
            )
            rec_us = load_us_recommendations(watch)
            if rec_us.empty:
                st.info("현재 매수 추천 기준을 충족하는 종목이 없습니다.")
            else:
                st.dataframe(rec_us, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("""
    **신호 기준 안내**
    | 신호 | 점수 | 조건 |
    |------|------|------|
    | 🟢 강력 매수 | 4+ | RSI 과매도 + MACD 골든크로스 + 이평선 위 |
    | 🔵 매수 | 2~3 | 복수의 매수 지표 충족 |
    | ⚪ 관망 | 0~1 | 혼조 |
    | 🟠 매도 | -1~-2 | 약세 지표 |
    | 🔴 강력 매도 | -3 이하 | 복수의 매도 지표 충족 |

    > ⚠️ 본 추천은 기술적 분석만을 기반으로 하며, 투자 손실에 대한 책임은 본인에게 있습니다.
    """)


# ══════════════════════════════════════════════════════════
# 주요 뉴스
# ══════════════════════════════════════════════════════════
elif menu == "📰 주요 뉴스":
    st.title("📰 오늘의 주요 금융 뉴스")

    with st.spinner("뉴스 로딩 중..."):
        articles = load_news()

    if not articles:
        st.warning("뉴스를 불러올 수 없습니다.")
    else:
        sources = list(set(a["출처"] for a in articles))
        selected = st.multiselect("출처 필터", sources, default=sources)

        for art in articles:
            if art["출처"] in selected:
                with st.container():
                    st.markdown(f"""
**[{art['제목']}]({art['링크']})**
`{art['출처']}` · {art['날짜']}
""")
                    st.divider()
