import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# 티커 → 한국어 회사명 매핑
TICKER_NAMES = {
    "AAPL": "애플", "MSFT": "마이크로소프트", "NVDA": "엔비디아", "AMZN": "아마존",
    "GOOGL": "구글", "META": "메타", "TSLA": "테슬라", "AVGO": "브로드컴",
    "BRK-B": "버크셔해서웨이", "JPM": "JP모건", "LLY": "일라이릴리", "V": "비자",
    "UNH": "유나이티드헬스", "XOM": "엑슨모빌", "MA": "마스터카드", "JNJ": "존슨앤존슨",
    "PG": "P&G", "HD": "홈디포", "COST": "코스트코", "ABBV": "애브비",
    "MRK": "머크", "WMT": "월마트", "CVX": "쉐브론", "BAC": "뱅크오브아메리카",
    "KO": "코카콜라", "PEP": "펩시코", "NFLX": "넷플릭스", "CRM": "세일즈포스",
    "AMD": "AMD", "ORCL": "오라클", "MCD": "맥도날드", "CSCO": "시스코",
    "NKE": "나이키", "IBM": "IBM", "QCOM": "퀄컴", "GE": "GE",
    "CAT": "캐터필러", "SBUX": "스타벅스", "GS": "골드만삭스", "MS": "모건스탠리",
    "PYPL": "페이팔", "UBER": "우버", "ABNB": "에어비앤비", "SNAP": "스냅",
    "RIVN": "리비안", "PLTR": "팔란티어", "SOFI": "소파이", "COIN": "코인베이스",
    "HOOD": "로빈후드", "SPY": "S&P500 ETF", "QQQ": "나스닥100 ETF",
    "GLD": "금 ETF", "MRNA": "모더나", "PFE": "화이자", "BNTX": "바이오엔텍",
    "TSM": "TSMC", "ASML": "ASML", "TM": "토요타", "SONY": "소니",
    "BABA": "알리바바", "JD": "징동닷컴", "PDD": "핀둬둬", "BIDU": "바이두",
    "NIO": "니오", "XPEV": "샤오펑", "LI": "리오토",
}

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

        result["회사명"] = result["티커"].map(lambda t: TICKER_NAMES.get(t, t))
        result = result[result["현재가"] > 0]
        cols = ["티커", "회사명", "현재가", "등락률", "거래량"]
        gainers = result.nlargest(top_n, "등락률")[cols].reset_index(drop=True)
        losers = result.nsmallest(top_n, "등락률")[cols].reset_index(drop=True)

        return gainers, losers
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()


def get_stock_history(ticker: str, period: str = "3mo"):
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        return df
    except:
        return pd.DataFrame()
