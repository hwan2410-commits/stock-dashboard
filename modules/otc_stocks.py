import requests
import pandas as pd
from datetime import datetime, timedelta
import json as _json

API_URL = "https://www.k-otc.or.kr/public/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json; charset=UTF-8",
    "Referer": "https://www.k-otc.or.kr/",
}

# selType 정의
# 1=시가총액 기준 전체 종목, 3=거래대금 상위, 4=거래량 상위, 5=주가 상승, 6=주가 하락


def _post(class_name: str, method: str, param: dict) -> dict:
    payload = _json.dumps({"class": class_name, "method": method, "session": False, "param": param})
    r = requests.post(API_URL, headers=HEADERS, data=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_rank(sel_type: str) -> list:
    today = datetime.now().strftime("%Y%m%d")
    data = _post("InvestService", "selectRankInfoItem", {
        "groupGb": "", "assignTyp": "", "currentEntgb": "",
        "standardDt": today, "selType": sel_type,
    })
    return data.get("contents") or []


def get_kotc_movers(top_n: int = 10):
    """K-OTC 상승/하락 상위 종목 (selType=5/6)"""
    try:
        gainers_raw = _fetch_rank("5")  # 주가 상승 종목
        losers_raw = _fetch_rank("6")   # 주가 하락 종목

        def _to_df(rows, sign=1):
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                "SHORTCD": "종목코드",
                "KOREANSHTNM": "종목명",
                "LASTCOT": "현재가",
                "RATE1": "등락률",
                "TRADEACMQTY": "거래량",
                "TRADEACMAMT": "거래대금",
                "BEFOREDAYCMP": "전일대비",
            })
            for col in ("현재가", "등락률", "거래량"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            cols = [c for c in ["종목코드", "종목명", "현재가", "등락률", "전일대비", "거래량"] if c in df.columns]
            return df[cols].head(top_n).reset_index(drop=True)

        return _to_df(gainers_raw), _to_df(losers_raw)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def get_kotc_listings() -> pd.DataFrame:
    """K-OTC 거래대금 상위 활성 종목 목록 (selType=3)"""
    try:
        rows = _fetch_rank("3")
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "SHORTCD": "종목코드",
            "KOREANSHTNM": "종목명",
            "LASTCOT": "현재가",
            "WEIGHTAVGCOT": "가중평균가",
            "BEFOREDAYCMP": "전일대비",
            "TRADEACMQTY": "거래량",
            "TRADEACMAMT": "거래대금",
        })
        for col in ("현재가", "전일대비", "거래량", "거래대금"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # 등락률 계산 (전일가 = 현재가 - 전일대비)
        if "현재가" in df.columns and "전일대비" in df.columns:
            prev = df["현재가"] - df["전일대비"]
            df["등락률"] = (df["전일대비"] / prev * 100).round(2)
        return df
    except Exception:
        return pd.DataFrame()


def get_kotc_summary() -> dict:
    """K-OTC 시장 전체 요약 통계"""
    try:
        # 전체 종목 = selType=1 (시가총액 기준)
        all_rows = _fetch_rank("1")
        gainers_rows = _fetch_rank("5")
        losers_rows = _fetch_rank("6")
        total = len(all_rows)
        up = len(gainers_rows)
        down = len(losers_rows)
        flat = total - up - down

        summary = {
            "종목수": total,
            "상승": up,
            "하락": down,
            "보합": max(flat, 0),
        }
        # 시가총액 합계
        if all_rows and "AMT1" in all_rows[0]:
            total_mktcap = sum(r.get("AMT1") or 0 for r in all_rows)
            summary["시가총액합계"] = int(total_mktcap)
        return summary
    except Exception:
        return {}


def search_kotc_stock(keyword: str) -> pd.DataFrame:
    """종목명 또는 코드로 K-OTC 종목 검색 (전체 종목에서 필터)"""
    try:
        rows = _fetch_rank("1")  # 전체 종목
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "SHORTCD": "종목코드",
            "KOREANSHTNM": "종목명",
            "WEIGHTAVGCOT": "현재가",
            "RATE1": "시총비중(%)",
            "TRADEACMQTY": "거래량",
            "AMT1": "시가총액",
        })
        kw = keyword.strip().lower()
        mask = pd.Series(False, index=df.index)
        if "종목명" in df.columns:
            mask |= df["종목명"].astype(str).str.lower().str.contains(kw, na=False)
        if "종목코드" in df.columns:
            mask |= df["종목코드"].astype(str).str.lower().str.contains(kw, na=False)
        result = df[mask].reset_index(drop=True)
        cols = [c for c in ["종목코드", "종목명", "현재가", "시총비중(%)", "거래량", "시가총액"] if c in result.columns]
        return result[cols]
    except Exception:
        return pd.DataFrame()


def _get_item_cd(short_cd: str) -> str:
    """shortCd → ISIN(itemCd) 조회"""
    try:
        today = datetime.now().strftime("%Y%m%d")
        data = _post("ItemService", "getToIfItemtradeV03", {
            "shortCd": short_cd, "standardDt": today,
        })
        contents = data.get("contents") or {}
        return contents.get("ITEMCD", "")
    except Exception:
        return ""


def get_kotc_stock_history(short_cd: str, days: int = 90) -> pd.DataFrame:
    """K-OTC 개별 종목 일별 시세 (Close + Volume)"""
    try:
        item_cd = _get_item_cd(short_cd)
        end = datetime.now()
        start = end - timedelta(days=days)
        data = _post("ItemService", "getDailyitemChart", {
            "shortCd": short_cd,
            "itemCd": item_cd,
            "startDt": start.strftime("%Y%m%d"),
            "endDt": end.strftime("%Y%m%d"),
        })
        items = data.get("contents") or []
        if not items:
            return pd.DataFrame()

        df = pd.DataFrame(items)
        df["Date"] = pd.to_datetime(df["STANDARDDT"], format="%Y%m%d")
        df = df.set_index("Date").sort_index()

        df["Close"] = pd.to_numeric(df["WEIGHTAVGCOT"], errors="coerce")
        df["Volume"] = pd.to_numeric(df["TRADEACMQTY"], errors="coerce")
        df["BfdayCmp"] = pd.to_numeric(df["WEIGHTAVGBFDAYCMP"], errors="coerce").fillna(0)
        df["Open"] = df["Close"] - df["BfdayCmp"]
        df["High"] = df[["Close", "Open"]].max(axis=1)
        df["Low"] = df[["Close", "Open"]].min(axis=1)

        return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()
