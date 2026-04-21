import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime, timedelta


def get_market_movers(market="KOSPI", top_n=10):
    """상승/하락 상위 종목 반환"""
    try:
        df = fdr.StockListing(market)
        df = df[df["Volume"] > 0].copy()
        df = df.rename(columns={
            "Code": "티커",
            "Name": "종목명",
            "Close": "종가",
            "ChagesRatio": "등락률",
            "Volume": "거래량",
        })
        df["등락률"] = df["등락률"].round(2)

        gainers = df.nlargest(top_n, "등락률")[["티커", "종목명", "종가", "등락률", "거래량"]].reset_index(drop=True)
        losers  = df.nsmallest(top_n, "등락률")[["티커", "종목명", "종가", "등락률", "거래량"]].reset_index(drop=True)

        return gainers, losers
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def get_stock_detail(ticker: str, days: int = 90):
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
        return df  # columns: Open, High, Low, Close, Volume, Change
    except Exception:
        return pd.DataFrame()


def get_ticker_name(ticker: str) -> str:
    """종목 코드 → 종목명"""
    try:
        for market in ("KOSPI", "KOSDAQ"):
            listing = fdr.StockListing(market)
            row = listing[listing["Code"] == ticker]
            if not row.empty:
                return row.iloc[0]["Name"]
    except Exception:
        pass
    return ticker
