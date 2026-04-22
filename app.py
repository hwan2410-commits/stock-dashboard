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
from modules.otc_stocks import get_kotc_movers, get_kotc_listings, get_kotc_stock_history, search_kotc_stock, get_kotc_summary
from modules.afterhours import get_kr_afterhours, get_us_afterhours

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
        ["🏠 홈 / 시장 요약", "🇰🇷 한국 주식", "🇺🇸 미국 주식", "🏦 장외/시간외 거래", "💡 매매 추천", "📰 주요 뉴스"],
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

@st.cache_data(ttl=300)
def load_kr_recommendations(tickers: tuple, names: tuple):
    return get_kr_recommendations(list(tickers), dict(names))

@st.cache_data(ttl=1800)
def load_us_recommendations(watch: tuple):
    return get_us_recommendations(list(watch))

@st.cache_data(ttl=600)
def load_kotc_movers(n):
    return get_kotc_movers(n)

@st.cache_data(ttl=600)
def load_kotc_listings():
    return get_kotc_listings()

@st.cache_data(ttl=600)
def load_kotc_history(short_cd, days):
    return get_kotc_stock_history(short_cd, days)

@st.cache_data(ttl=600)
def load_kotc_summary():
    return get_kotc_summary()

@st.cache_data(ttl=120)
def load_kr_afterhours(n):
    return get_kr_afterhours(n)

@st.cache_data(ttl=120)
def load_us_afterhours(n):
    return get_us_afterhours(n)


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
# 장외 / 시간외 거래
# ══════════════════════════════════════════════════════════
elif menu == "🏦 장외/시간외 거래":
    st.title("🏦 장외/시간외 거래")

    tab_ah_kr, tab_ah_us, tab_kotc1, tab_kotc2, tab_kotc3 = st.tabs([
        "⏰ 시간외 한국", "🌙 시간외 미국", "📊 K-OTC 현황", "🔍 K-OTC 검색", "📈 K-OTC 차트"
    ])

    # ── 시간외 한국 ────────────────────────────────────────
    with tab_ah_kr:
        st.markdown("#### ⏰ 한국 주식 시간외 단일가")
        st.caption("KOSPI·KOSDAQ 시가총액 상위 100개 종목 기준 / 장전(08:00~09:00) · 장후(15:30~18:00) 시간외 단일가 체결 현황")
        with st.spinner("시간외 데이터 로딩 중..."):
            kr_vol, kr_rate, session_type = load_kr_afterhours(top_n)

        session_label = "🌅 장전 시간외" if session_type == "PRE_MARKET" else "🌆 장후 시간외"
        st.info(f"현재 세션: **{session_label}** | 한국 시간외 단일가는 당일 종가로 체결되므로 별도 가격 변동이 없습니다.")

        if kr_vol.empty:
            st.warning("시간외 거래량 데이터가 없습니다. 정규장 시간 중이거나 시간외 거래가 없을 수 있습니다.")
        else:
            st.markdown("#### 📊 시간외 거래량 TOP")
            st.dataframe(kr_vol, use_container_width=True, hide_index=True)

        st.divider()

        if not kr_rate.empty:
            st.markdown("#### 📈 시간외 거래 종목 중 정규장 등락률 상위")
            st.dataframe(kr_rate, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("""
        **한국 시간외 거래 안내**
        | 구분 | 시간 | 방식 |
        |------|------|------|
        | 장전 시간외 | 08:00 ~ 09:00 | 전일 종가 기준 단일가 |
        | 장후 시간외 | 15:30 ~ 18:00 | 당일 종가 기준 단일가 |

        > ⚠️ 한국 시간외 단일가 거래는 **종가가 고정**되어 있어 가격 변동이 없습니다. 시간외에 얼마나 활발히 거래됐는지(거래량)가 핵심 지표입니다.
        """)

    # ── 시간외 미국 ────────────────────────────────────────
    with tab_ah_us:
        st.markdown("#### 🌙 미국 주식 시간외 시세")
        st.caption("프리마켓(4:00~9:30 ET) · 애프터마켓(16:00~20:00 ET) 기준 정규장 종가 대비 변화")
        with st.spinner("미국 시간외 데이터 로딩 중..."):
            us_df, us_session = load_us_afterhours(top_n)

        st.info(f"현재 세션: **{us_session}**")

        if us_df.empty:
            st.warning("미국 시간외 데이터를 불러오지 못했습니다.")
        else:
            # 상승/하락 분리
            has_rate = us_df["등락률(%)"].notna()
            us_g = us_df[has_rate & (us_df["등락률(%)"] >= 0)].head(top_n)
            us_l = us_df[has_rate & (us_df["등락률(%)"] < 0)].sort_values("등락률(%)").head(top_n)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🔴 시간외 상승")
                st.dataframe(us_g, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("#### 🔵 시간외 하락")
                st.dataframe(us_l, use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### 전체 종목 시간외 시세")
            st.dataframe(us_df, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("""
        **미국 시간외 거래 안내**
        | 구분 | 시간 (ET) | 한국시간 (KST) |
        |------|-----------|----------------|
        | 프리마켓 | 04:00 ~ 09:30 | 17:00 ~ 22:30 |
        | 정규장 | 09:30 ~ 16:00 | 22:30 ~ 05:00+1 |
        | 애프터마켓 | 16:00 ~ 20:00 | 05:00 ~ 09:00+1 |
        """)

    # ── K-OTC 시장 현황 ───────────────────────────────────
    with tab_kotc1:
        st.markdown('<div class="section-header">📊 K-OTC 시장 요약</div>', unsafe_allow_html=True)

        with st.spinner("K-OTC 데이터 로딩 중..."):
            summary = load_kotc_summary()
            kotc_g, kotc_l = load_kotc_movers(top_n)

        if summary:
            m_cols = st.columns(4)
            m_cols[0].metric("전체 종목수", f"{summary.get('종목수', '-')}개")
            m_cols[1].metric("🔴 상승", f"{summary.get('상승', '-')}종목")
            m_cols[2].metric("🔵 하락", f"{summary.get('하락', '-')}종목")
            m_cols[3].metric("⚪ 보합", f"{summary.get('보합', '-')}종목")

            if "시가총액합계" in summary and summary["시가총액합계"] > 0:
                mktcap = summary["시가총액합계"]
                mktcap_str = f"{mktcap / 1_000_000_000_000:.1f}조원" if mktcap >= 1_000_000_000_000 else f"{mktcap / 100_000_000:.0f}억원"
                st.info(f"K-OTC 총 시가총액: {mktcap_str}")
        else:
            st.warning("K-OTC 시장 요약 데이터를 불러오지 못했습니다.")

        st.divider()
        st.markdown('<div class="section-header">🔴 상승 / 🔵 하락 TOP</div>', unsafe_allow_html=True)

        if kotc_g.empty and kotc_l.empty:
            st.error("K-OTC 데이터를 불러오지 못했습니다. 장 마감 후이거나 API 응답 구조가 변경되었을 수 있습니다.")
            st.markdown("직접 확인: [K-OTC 공식 홈페이지](https://www.k-otc.or.kr)")
        else:
            render_movers_table(kotc_g, kotc_l, col_price="현재가", col_change="등락률")

        st.divider()
        st.markdown('<div class="section-header">📋 전체 종목 목록</div>', unsafe_allow_html=True)
        with st.spinner("전체 종목 불러오는 중..."):
            all_df = load_kotc_listings()
        if all_df.empty:
            st.info("전체 종목 데이터를 불러오지 못했습니다.")
        else:
            show_cols = [c for c in ["종목코드", "종목명", "현재가", "등락률", "거래량", "시가총액"] if c in all_df.columns]
            display_df = all_df[show_cols].sort_values("등락률", ascending=False) if "등락률" in all_df.columns else all_df[show_cols]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

    with tab_kotc2:
        st.markdown("#### 🔍 K-OTC 종목 검색")
        keyword = st.text_input("종목명 또는 종목코드 입력", placeholder="예: 카카오, 003240")
        if keyword:
            with st.spinner("검색 중..."):
                result_df = search_kotc_stock(keyword)
            if result_df.empty:
                st.warning(f"'{keyword}' 검색 결과가 없습니다.")
            else:
                show_cols = [c for c in ["종목코드", "종목명", "현재가", "등락률", "거래량", "시가총액"] if c in result_df.columns]
                st.dataframe(result_df[show_cols], use_container_width=True, hide_index=True)

    with tab_kotc3:
        st.markdown("#### 📈 K-OTC 종목 차트")
        c1, c2 = st.columns([3, 1])
        otc_code = c1.text_input("종목코드 입력 (K-OTC)", placeholder="예: KQ1234567")
        otc_period_map = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}
        otc_period_label = c2.selectbox("기간", list(otc_period_map.keys()), index=1, key="otc_period")

        if otc_code:
            with st.spinner("차트 로딩 중..."):
                otc_df = load_kotc_history(otc_code, otc_period_map[otc_period_label])
            if otc_df.empty:
                st.warning("해당 종목의 차트 데이터를 불러오지 못했습니다. 종목코드를 확인하세요.")
            else:
                render_candlestick(otc_df, f"K-OTC {otc_code} 캔들차트")
                if len(otc_df) >= 20:
                    sig = compute_signals(otc_df)
                    if sig:
                        st.markdown("**기술적 분석 신호**")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("매매 신호", sig["신호"])
                        col2.metric("RSI", sig["RSI"])
                        col3.metric("현재가", f"{sig['현재가']:,}")
                        col4.metric("20일 이평선", f"{sig['20일선']:,}")
                        st.info(f"근거: {sig['이유']}")

    st.divider()
    st.markdown("""
    > ℹ️ **K-OTC란?** 금융투자협회가 운영하는 장외주식 거래 플랫폼으로, KOSPI·KOSDAQ에 상장되지 않은 비상장 주식을 거래할 수 있습니다.
    > 비상장 주식 특성상 유동성이 낮고 가격 변동성이 높을 수 있습니다. 투자에 유의하세요.
    """)


# ══════════════════════════════════════════════════════════
# 매매 추천
# ══════════════════════════════════════════════════════════
elif menu == "💡 매매 추천":
    st.title("💡 오늘의 매매 추천 종목")
    st.caption("RSI, MACD, 이동평균선 기반 기술적 분석 결과입니다. 투자 판단의 참고 자료로만 활용하세요.")

    tab1, tab2 = st.tabs(["🇰🇷 한국 추천", "🇺🇸 미국 추천"])

    # KOSPI + KOSDAQ 주요 종목 고정 목록 (100개)
    KR_WATCHLIST = {
        # KOSPI 대형주
        "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차",
        "035420": "NAVER", "000270": "기아", "051910": "LG화학",
        "006400": "삼성SDI", "035720": "카카오", "068270": "셀트리온",
        "028260": "삼성물산", "012330": "현대모비스", "055550": "신한지주",
        "105560": "KB금융", "096770": "SK이노베이션", "003550": "LG",
        "015760": "한국전력", "086790": "하나금융지주", "032830": "삼성생명",
        "018260": "삼성에스디에스", "009150": "삼성전기", "051900": "LG생활건강",
        "017670": "SK텔레콤", "030200": "KT", "000810": "삼성화재",
        "066570": "LG전자", "034730": "SK", "011170": "롯데케미칼",
        "047050": "포스코인터내셔널", "032640": "LG유플러스", "033780": "KT&G",
        "003490": "대한항공", "010130": "고려아연", "004020": "현대제철",
        "010950": "S-Oil", "011790": "SKC", "024110": "기업은행",
        "009240": "한샘", "000100": "유한양행", "271560": "오리온",
        "316140": "우리금융지주", "086280": "현대글로비스", "011040": "CJ대한통운",
        "181710": "NHN", "207940": "삼성바이오로직스", "005490": "POSCO홀딩스",
        "042660": "한화오션", "000720": "현대건설", "097950": "CJ제일제당",
        "003240": "태광산업", "010140": "삼성중공업", "004170": "신세계",
        "029780": "삼성카드", "000120": "CJ대한통운", "011200": "HMM",
        "021240": "코웨이", "002380": "KCC", "001800": "오리온홀딩스",
        "004990": "롯데지주", "000230": "일동홀딩스", "002790": "아모레G",
        "034020": "두산에너빌리티", "015020": "이수화학", "005440": "현대그린푸드",
        "000650": "천일고속", "004800": "효성", "003670": "포스코퓨처엠",
        "011070": "LG이노텍", "007070": "GS리테일", "002070": "흥아해운",
        "005810": "풍산", "003830": "대한화섬", "000490": "대동",
        "002860": "한국콜마홀딩스", "008770": "호텔신라", "030000": "제일기획",
        "000080": "하이트진로", "007310": "오뚜기", "002240": "고려산업",
        # KOSDAQ 주요종목
        "247540": "에코프로비엠", "091990": "셀트리온헬스케어", "196170": "알테오젠",
        "357780": "솔브레인", "326030": "SK바이오팜", "145020": "휴젤",
        "263750": "펄어비스", "112040": "위메이드", "039030": "이오테크닉스",
        "036570": "엔씨소프트", "035900": "JYP Ent", "028300": "HLB",
        "214150": "클래시스", "058470": "리노공업", "086900": "메디톡스",
        "068760": "셀트리온제약", "041510": "에스엠", "095340": "ISC",
        "067160": "아프리카TV", "122870": "와이지엔터테인먼트",
    }

    with tab1:
        with st.spinner("한국 주식 분석 중... (캐시 없을 시 1~2분 소요)"):
            top_tickers = tuple(KR_WATCHLIST.keys())
            names_tuple = tuple(KR_WATCHLIST.items())
            try:
                rec_df = load_kr_recommendations(top_tickers, names_tuple)
                if rec_df.empty:
                    st.info("현재 매수 추천 기준을 충족하는 종목이 없습니다.")
                else:
                    st.dataframe(rec_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"분석 오류: {e}")

    with tab2:
        with st.spinner("미국 주식 분석 중... (캐시 없을 시 20~30초 소요)"):
            watch = (
                "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                "AMD", "INTC", "NFLX", "PYPL", "UBER", "CRM", "ORCL", "ADBE",
                "COIN", "PLTR", "SOFI", "RIVN", "SHOP", "SNOW", "RBLX", "HOOD",
                "ABNB", "DASH", "LYFT", "SNAP", "PINS", "TWLO", "DDOG",
                "ARM", "SMCI", "MU", "QCOM", "AVGO", "NOW", "PANW", "ZS",
                "MSTR", "IONQ", "RXRX", "SOUN", "BBAI", "ARKG", "ARKK",
                "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "SQ",
            )
            rec_us = load_us_recommendations(watch)
            if rec_us.empty:
                st.info("현재 매수 추천 기준을 충족하는 종목이 없습니다.")
            else:
                st.dataframe(rec_us, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("""
    **신호 기준 안내** (14가지 지표 종합, 점수 범위: -14 ~ +14)
    | 신호 | 점수 | 의미 |
    |------|------|------|
    | 🟢 강력 매수 | 10+ | 다수 매수 지표 동시 충족 |
    | 🔵 매수 | 4~9 | 복수의 매수 지표 충족 |
    | ⚪ 관망 | -3~3 | 혼조 / 추세 불명확 |
    | 🟠 매도 | -4~-7 | 복수의 매도 지표 충족 |
    | 🔴 강력 매도 | -8 이하 | 다수 매도 지표 동시 충족 |

    **활용 지표 14가지**: RSI · MACD(+히스토그램) · 볼린저밴드 · 스토캐스틱 · 5/20/60/120일 이평선 · 이평선 정배열 · 거래량 · ADX · CCI · Williams %R · 52주 위치

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
