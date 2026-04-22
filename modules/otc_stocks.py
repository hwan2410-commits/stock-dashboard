import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

KOTC_BASE = "https://www.k-otc.or.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.k-otc.or.kr/mktstat/stockInfo.do",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def get_kotc_listings() -> pd.DataFrame:
    """K-OTC 전체 종목 시세 조회"""
    try:
        url = f"{KOTC_BASE}/mktstat/stockInfoSub.json"
        payload = {
            "selType": "total",
            "pageIndex": "1",
            "pageUnit": "200",
        }
        r = requests.post(url, headers=HEADERS, data=payload, timeout=15)
        r.raise_for_status()
        data = r.json()

        # 응답 구조에 따라 리스트 추출
        rows = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("list", "data", "result", "stockList", "items"):
                if key in data and isinstance(data[key], list):
                    rows = data[key]
                    break

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        return _normalize_kotc_df(df)

    except Exception:
        return _fallback_html_scrape()


def _fallback_html_scrape() -> pd.DataFrame:
    """JSON API 실패 시 HTML 테이블 파싱 시도"""
    try:
        url = f"{KOTC_BASE}/mktstat/stockInfo.do"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        tables = pd.read_html(StringIO(r.text), encoding="utf-8")
        for tbl in tables:
            if len(tbl.columns) >= 5 and len(tbl) > 5:
                return _normalize_kotc_df(tbl)
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _normalize_kotc_df(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명을 한국어로 통일"""
    col_map = {}
    for col in df.columns:
        col_str = str(col).lower()
        if any(k in col_str for k in ("isucd", "code", "종목코드", "stockcode")):
            col_map[col] = "종목코드"
        elif any(k in col_str for k in ("isunm", "name", "종목명", "stockname")):
            col_map[col] = "종목명"
        elif any(k in col_str for k in ("clsprc", "close", "현재가", "종가")):
            col_map[col] = "현재가"
        elif any(k in col_str for k in ("flctrt", "change", "등락률", "chng_rt")):
            col_map[col] = "등락률"
        elif any(k in col_str for k in ("trqu", "volume", "거래량")):
            col_map[col] = "거래량"
        elif any(k in col_str for k in ("tramt", "amount", "거래대금")):
            col_map[col] = "거래대금"
        elif any(k in col_str for k in ("mktcap", "시가총액")):
            col_map[col] = "시가총액"
        elif any(k in col_str for k in ("opnprc", "open", "시가")):
            col_map[col] = "시가"
        elif any(k in col_str for k in ("hgprc", "high", "고가")):
            col_map[col] = "고가"
        elif any(k in col_str for k in ("lwprc", "low", "저가")):
            col_map[col] = "저가"

    df = df.rename(columns=col_map)

    for num_col in ("현재가", "등락률", "거래량", "거래대금", "시가총액"):
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(
                df[num_col].astype(str).str.replace(",", "").str.replace("%", ""),
                errors="coerce",
            )

    return df


def get_kotc_movers(top_n: int = 10):
    """K-OTC 상승/하락 상위 종목"""
    df = get_kotc_listings()
    if df.empty or "등락률" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    df = df.dropna(subset=["등락률"])
    cols = [c for c in ["종목코드", "종목명", "현재가", "등락률", "거래량"] if c in df.columns]
    gainers = df.nlargest(top_n, "등락률")[cols].reset_index(drop=True)
    losers = df.nsmallest(top_n, "등락률")[cols].reset_index(drop=True)
    return gainers, losers


def search_kotc_stock(keyword: str) -> pd.DataFrame:
    """종목명 또는 코드로 K-OTC 종목 검색"""
    df = get_kotc_listings()
    if df.empty:
        return pd.DataFrame()

    kw = keyword.strip().lower()
    mask = pd.Series([False] * len(df), index=df.index)
    if "종목명" in df.columns:
        mask |= df["종목명"].astype(str).str.lower().str.contains(kw, na=False)
    if "종목코드" in df.columns:
        mask |= df["종목코드"].astype(str).str.lower().str.contains(kw, na=False)

    return df[mask].reset_index(drop=True)


def get_kotc_stock_history(code: str, days: int = 90) -> pd.DataFrame:
    """K-OTC 개별 종목 시세 조회 (일별)"""
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        url = f"{KOTC_BASE}/mktstat/stockHistSub.json"
        payload = {
            "isuCd": code,
            "strtDd": start.strftime("%Y%m%d"),
            "endDd": end.strftime("%Y%m%d"),
        }
        r = requests.post(url, headers=HEADERS, data=payload, timeout=15)
        r.raise_for_status()
        data = r.json()

        rows = None
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("list", "data", "result", "histList"):
                if key in data and isinstance(data[key], list):
                    rows = data[key]
                    break

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df = _normalize_kotc_df(df)

        # 날짜 컬럼 표준화
        for date_col in ("일자", "date", "basDd", "trdDd"):
            if date_col in df.columns:
                df.index = pd.to_datetime(df[date_col].astype(str), format="%Y%m%d", errors="coerce")
                df = df.drop(columns=[date_col])
                break

        return df.sort_index()
    except Exception:
        return pd.DataFrame()


def get_kotc_summary() -> dict:
    """K-OTC 시장 전체 요약 통계"""
    df = get_kotc_listings()
    if df.empty:
        return {}

    summary = {"종목수": len(df)}
    if "등락률" in df.columns:
        pos = (df["등락률"] > 0).sum()
        neg = (df["등락률"] < 0).sum()
        neu = (df["등락률"] == 0).sum()
        summary.update({"상승": int(pos), "하락": int(neg), "보합": int(neu)})
    if "거래대금" in df.columns:
        summary["총거래대금"] = int(df["거래대금"].sum())
    if "시가총액" in df.columns:
        summary["시가총액합계"] = int(df["시가총액"].sum())
    return summary
