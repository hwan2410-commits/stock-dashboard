import requests
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
import pytz
from datetime import datetime, timedelta

NAVER_POLLING = "https://polling.finance.naver.com/api/realtime/domestic/stock/{codes}"
NAVER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

US_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
    "AMD", "INTC", "NFLX", "PYPL", "UBER", "CRM", "ORCL", "ADBE",
    "COIN", "PLTR", "SOFI", "RIVN", "SHOP",
]

US_NAMES = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존",
    "GOOGL": "구글", "META": "메타", "TSLA": "테슬라", "AMD": "AMD",
    "INTC": "인텔", "NFLX": "넷플릭스", "PYPL": "페이팔", "UBER": "우버",
    "CRM": "세일즈포스", "ORCL": "오라클", "ADBE": "어도비", "COIN": "코인베이스",
    "PLTR": "팔란티어", "SOFI": "소파이", "RIVN": "리비안", "SHOP": "쇼피파이",
}


def _naver_batch(codes: list) -> list:
    """Naver 실시간 API 배치 조회 (최대 50개)"""
    code_str = ",".join(codes[:50])
    r = requests.get(NAVER_POLLING.format(codes=code_str), headers=NAVER_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json().get("datas", [])


def _parse_num(s) -> float:
    """'1,234.56' 형태 문자열 → float"""
    if s is None:
        return float("nan")
    return float(str(s).replace(",", "").replace("%", "").strip() or "nan")


def get_kr_afterhours(top_n: int = 10):
    """한국 주식 시간외 단일가 현황

    한국 시간외 단일가는 당일/전일 종가로 거래되므로 가격 변동이 없습니다.
    대신 시간외 거래량 상위 및 당일 등락률 기준으로 정렬합니다.

    Returns:
        top_volume (DataFrame): 시간외 거래량 상위
        regular_movers (DataFrame): 정규장 등락률 기준
        session_type (str): 'PRE_MARKET' or 'AFTER_MARKET'
    """
    try:
        # KOSPI + KOSDAQ 상위 종목 코드 수집
        kospi = fdr.StockListing("KOSPI").nlargest(80, "Marcap")["Code"].tolist()
        kosdaq = fdr.StockListing("KOSDAQ").nlargest(20, "Marcap")["Code"].tolist()
        codes = list(dict.fromkeys(kospi + kosdaq))

        # 배치 조회 (최대 50개씩)
        all_items = []
        for i in range(0, len(codes), 50):
            all_items.extend(_naver_batch(codes[i:i + 50]))

        rows = []
        session_type = "AFTER_MARKET"
        for item in all_items:
            omi = item.get("overMarketPriceInfo")
            if not omi:
                continue
            session_type = omi.get("tradingSessionType", "AFTER_MARKET")

            over_vol = _parse_num(omi.get("accumulatedTradingVolume"))
            over_price = _parse_num(omi.get("overPrice"))
            regular_rate = _parse_num(item.get("fluctuationsRatioRaw"))
            regular_close = _parse_num(item.get("closePriceRaw"))
            prev_diff = _parse_num(item.get("compareToPreviousClosePriceRaw"))

            rows.append({
                "종목코드": item.get("itemCode", ""),
                "종목명": item.get("stockName", ""),
                "시간외가": int(over_price) if not pd.isna(over_price) else None,
                "정규장종가": int(regular_close) if not pd.isna(regular_close) else None,
                "정규장등락률(%)": regular_rate,
                "전일대비": int(prev_diff) if not pd.isna(prev_diff) else None,
                "시간외거래량": int(over_vol) if not pd.isna(over_vol) else 0,
                "세션": "장전" if session_type == "PRE_MARKET" else "장후",
            })

        if not rows:
            return pd.DataFrame(), pd.DataFrame(), session_type

        df = pd.DataFrame(rows)

        # 시간외 거래량 TOP (거래가 있는 종목)
        vol_cols = ["종목코드", "종목명", "시간외가", "정규장종가", "정규장등락률(%)", "시간외거래량"]
        top_vol = (df[df["시간외거래량"] > 0]
                   .nlargest(top_n, "시간외거래량")[vol_cols]
                   .reset_index(drop=True))

        # 정규장 등락률 기준 상위 (시간외 거래가 있는 종목만)
        rate_cols = ["종목코드", "종목명", "정규장종가", "정규장등락률(%)", "전일대비", "시간외거래량"]
        active = df[df["시간외거래량"] > 0]
        top_rate = (active.nlargest(top_n, "정규장등락률(%)")[rate_cols]
                    .reset_index(drop=True)) if not active.empty else pd.DataFrame()

        return top_vol, top_rate, session_type

    except Exception:
        return pd.DataFrame(), pd.DataFrame(), "AFTER_MARKET"


def get_us_afterhours(top_n: int = 10):
    """미국 주요 종목 시간외 (프리마켓/애프터마켓) 시세

    Returns:
        df (DataFrame with pre/post prices), session_label (str)
    """
    try:
        df_raw = yf.download(
            US_WATCHLIST, period="1d", interval="1m",
            prepost=True, progress=False, auto_adjust=True,
        )
        if df_raw.empty:
            return pd.DataFrame(), "시간외"

        close = df_raw["Close"]
        if isinstance(close.columns, pd.MultiIndex):
            close.columns = close.columns.get_level_values(0)

        et = pytz.timezone("America/New_York")
        close.index = close.index.tz_convert(et)

        now_et = datetime.now(et)
        today_date = now_et.date()
        regular_start = et.localize(datetime(today_date.year, today_date.month, today_date.day, 9, 30))
        regular_end   = et.localize(datetime(today_date.year, today_date.month, today_date.day, 16, 0))

        pre_mask     = close.index < regular_start
        regular_mask = (close.index >= regular_start) & (close.index <= regular_end)
        post_mask    = close.index > regular_end

        pre_close     = close[pre_mask].iloc[-1]     if pre_mask.any()     else pd.Series(dtype=float)
        regular_close = close[regular_mask].iloc[-1] if regular_mask.any() else pd.Series(dtype=float)
        post_close    = close[post_mask].iloc[-1]    if post_mask.any()    else pd.Series(dtype=float)

        # 현재 세션 판단
        if post_mask.any():
            session_label = "장후 (After-Hours)"
            ext_price = post_close
        elif pre_mask.any() and not regular_mask.any():
            session_label = "장전 (Pre-Market)"
            ext_price = pre_close
        else:
            session_label = "정규장 중"
            ext_price = regular_close

        # 비교 기준: 정규장 종가 (없으면 장전 기준 어제 종가는 yfinance 2d로 보완)
        base = regular_close if regular_mask.any() else pd.Series(dtype=float)

        rows = []
        for ticker in US_WATCHLIST:
            ext = ext_price.get(ticker)
            reg = base.get(ticker) if not base.empty else None
            if ext is None or pd.isna(ext):
                continue
            row = {
                "티커": ticker,
                "회사명": US_NAMES.get(ticker, ticker),
                "시간외가": round(float(ext), 2),
            }
            if reg and not pd.isna(reg):
                diff_pct = (ext - reg) / reg * 100
                row["정규장종가"] = round(float(reg), 2)
                row["등락률(%)"] = round(diff_pct, 2)
                row["전일대비"] = round(float(ext - reg), 2)
            else:
                row["정규장종가"] = None
                row["등락률(%)"] = float("nan")
                row["전일대비"] = None
            rows.append(row)

        if not rows:
            return pd.DataFrame(), session_label

        result = pd.DataFrame(rows)
        result = result.sort_values("등락률(%)", ascending=False, na_position="last").reset_index(drop=True)
        return result, session_label

    except Exception:
        return pd.DataFrame(), "시간외"
