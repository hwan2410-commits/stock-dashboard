import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# S&P 500 주요 종목 (대표 200개)
SP500_TICKERS = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","BRK-B","JPM",
    "LLY","V","UNH","XOM","MA","JNJ","PG","HD","COST","ABBV",
    "MRK","WMT","CVX","BAC","KO","PEP","NFLX","CRM","AMD","ORCL",
    "TMO","LIN","MCD","CSCO","ACN","ABT","NKE","TXN","DHR","NEE",
    "PM","ADBE","AMGN","MS","INTC","HON","IBM","QCOM","UPS","RTX",
    "GE","CAT","SBUX","LOW","SPGI","GILD","ELV","MDT","BLK","AXP",
    "ISRG","PLD","VRTX","GS","MMC","DE","T","SYK","REGN","BMY",
    "ZTS","CI","CB","SO","DUK","AON","TJX","BSX","MDLZ","ETN",
    "MO","ADI","PNC","HUM","KLAC","ADP","NSC","USB","ITW","F",
    "GM","PYPL","UBER","ABNB","SNAP","RIVN","PLTR","SOFI","HOOD","COIN",
    "SPY","QQQ","IWM","DIA","GLD","SLV","USO","TLT","HYG","LQD",
    "MRNA","PFE","BNTX","JNJ","AZN","GSK","NVO","SNY","BAYRY","RHHBY",
    "TSM","ASML","SAP","TM","SONY","NVS","UL","BP","SHEL","RIO",
    "BABA","JD","PDD","BIDU","NIO","XPEV","LI","SE","GRAB","GOTO",
]


def get_us_movers(top_n=10):
    """미국 주식 상승/하락 상위 종목"""
    try:
        tickers = list(dict.fromkeys(SP500_TICKERS))  # 중복 제거
        data = yf.download(tickers, period="2d", auto_adjust=True, progress=False)

        if data.empty:
            return pd.DataFrame(), pd.DataFrame()

        close = data["Close"]
        # yfinance MultiIndex 처리
        if isinstance(close.columns, pd.MultiIndex):
            close.columns = close.columns.get_level_values(0)
        if len(close) < 2:
            return pd.DataFrame(), pd.DataFrame()

        change_pct = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100).round(2)
        last_price = close.iloc[-1].round(2)
        volume = data["Volume"]
        if isinstance(volume.columns, pd.MultiIndex):
            volume.columns = volume.columns.get_level_values(0)
        volume = volume.iloc[-1]

        result = pd.DataFrame({
            "티커": change_pct.index,
            "현재가": last_price.values,
            "등락률": change_pct.values,
            "거래량": volume.values,
        }).dropna()

        result = result[result["현재가"] > 0]
        gainers = result.nlargest(top_n, "등락률").reset_index(drop=True)
        losers = result.nsmallest(top_n, "등락률").reset_index(drop=True)

        return gainers, losers
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()


def get_stock_history(ticker: str, period: str = "3mo"):
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        return df
    except:
        return pd.DataFrame()
