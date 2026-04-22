import requests
import pandas as pd
import FinanceDataReader as fdr
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _scrape_naver_sise(page_name: str, top_n: int) -> pd.DataFrame:
    """네이버 금융 시세 페이지(sise_rise/sise_fall 등) HTML 파싱"""
    url = f"https://finance.naver.com/sise/{page_name}.naver"
    rows = []
    for page in range(1, 6):  # 최대 5페이지까지
        r = requests.get(url, headers=NAVER_HEADERS, params={"page": page}, timeout=10)
        soup = BeautifulSoup(r.content, "lxml")
        for row in soup.select("table.type_2 tr"):
            cols = row.find_all("td")
            if len(cols) < 9:
                continue
            name_el = cols[1].find("a")
            if not name_el:
                continue
            try:
                href = name_el.get("href", "")
                code = href.split("code=")[-1] if "code=" in href else ""
                name = name_el.get_text(strip=True)
                price = int(cols[2].get_text(strip=True).replace(",", "") or 0)
                rate = float(cols[4].get_text(strip=True).replace("+", "").replace("%", "") or 0)
                volume = int(cols[8].get_text(strip=True).replace(",", "") or 0)
                if code and name and price:
                    rows.append({"티커": code, "종목명": name, "종가": price, "등락률": rate, "거래량": volume})
            except (ValueError, IndexError):
                continue
        if len(rows) >= top_n:
            break
    return pd.DataFrame(rows[:top_n])


def get_market_movers(market: str = "KOSPI", top_n: int = 10):
    """KOSPI/KOSDAQ 상승/하락 상위 종목 (네이버 금융 스크래핑)"""
    sosok = "0" if market == "KOSPI" else "1"
    try:
        gainers = _scrape_naver_sise(f"sise_rise.naver?sosok={sosok}&", top_n)
        losers  = _scrape_naver_sise(f"sise_fall.naver?sosok={sosok}&", top_n)
        return gainers, losers
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def get_stock_detail(ticker: str, days: int = 90) -> pd.DataFrame:
    """개별 종목 일별 OHLCV"""
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        return df
    except Exception:
        return pd.DataFrame()


def get_ticker_name(ticker: str) -> str:
    """종목 코드 → 종목명 (네이버 검색 우선, FDR 폴백)"""
    try:
        r = requests.get(
            "https://m.stock.naver.com/api/stocks/search",
            headers=NAVER_HEADERS,
            params={"keyword": ticker, "hits": 1},
            timeout=8,
        )
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                return items[0].get("name", ticker)
    except Exception:
        pass
    try:
        for mkt in ("KOSPI", "KOSDAQ"):
            listing = fdr.StockListing(mkt)
            row = listing[listing["Code"] == ticker]
            if not row.empty:
                return row.iloc[0]["Name"]
    except Exception:
        pass
    return ticker
