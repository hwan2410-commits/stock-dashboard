import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import ta


def _flatten_yf(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance MultiIndex 컬럼을 단일 레벨로 변환"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def compute_signals(df: pd.DataFrame) -> dict:
    """기술적 지표 계산 및 매매 신호 생성"""
    if df is None or len(df) < 20:
        return {}

    close = df["Close"] if "Close" in df.columns else df["종가"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna().astype(float)

    if len(close) < 20:
        return {}

    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(min(60, len(close))).mean().iloc[-1]
    current = close.iloc[-1]

    score = 0
    reasons = []

    if rsi < 35:
        score += 2
        reasons.append(f"RSI 과매도({rsi:.1f})")
    elif rsi < 50:
        score += 1
        reasons.append(f"RSI 중립({rsi:.1f})")
    elif rsi > 70:
        score -= 2
        reasons.append(f"RSI 과매수({rsi:.1f})")

    if macd > macd_signal:
        score += 2
        reasons.append("MACD 골든크로스")
    else:
        score -= 1
        reasons.append("MACD 데드크로스")

    if current > ma20:
        score += 1
        reasons.append("20일선 위")
    else:
        score -= 1
        reasons.append("20일선 아래")

    if current > ma60:
        score += 1
        reasons.append("60일선 위")
    else:
        score -= 1

    if score >= 4:
        signal, color = "강력 매수", "🟢"
    elif score >= 2:
        signal, color = "매수", "🔵"
    elif score <= -3:
        signal, color = "강력 매도", "🔴"
    elif score <= -1:
        signal, color = "매도", "🟠"
    else:
        signal, color = "관망", "⚪"

    return {
        "신호": f"{color} {signal}",
        "점수": score,
        "RSI": round(rsi, 1),
        "현재가": round(current, 2),
        "20일선": round(ma20, 2),
        "이유": ", ".join(reasons),
    }


def get_kr_recommendations(tickers: list, names: dict) -> pd.DataFrame:
    """한국 주식 추천 목록"""
    results = []
    start = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

    for ticker in tickers[:15]:
        try:
            df = fdr.DataReader(ticker, start)
            if df.empty:
                continue
            signals = compute_signals(df)
            if signals and signals["점수"] >= 2:
                signals["종목명"] = names.get(ticker, ticker)
                signals["티커"] = ticker
                results.append(signals)
        except:
            continue

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)[["종목명", "티커", "신호", "점수", "RSI", "현재가", "20일선", "이유"]]
    return df_result.sort_values("점수", ascending=False).reset_index(drop=True)


def get_us_recommendations(tickers: list) -> pd.DataFrame:
    """미국 주식 추천 목록 (배치 다운로드로 속도 개선)"""
    watch_list = tickers[:20] if tickers else [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
        "AMD", "INTC", "NFLX", "PYPL", "UBER", "CRM", "ORCL", "ADBE"
    ]

    try:
        # 한번에 모든 종목 다운로드 (개별 호출 대신 배치)
        data = yf.download(watch_list, period="6mo", auto_adjust=True, progress=False, group_by="ticker")
    except Exception:
        return pd.DataFrame()

    results = []
    for ticker in watch_list:
        try:
            # group_by="ticker" 사용 시 data[ticker] 로 접근
            if ticker in data.columns.get_level_values(0):
                df_ticker = data[ticker].copy()
            else:
                continue

            df_ticker = _flatten_yf(df_ticker).dropna(subset=["Close"])
            signals = compute_signals(df_ticker)
            if signals and signals["점수"] >= 2:
                signals["티커"] = ticker
                results.append(signals)
        except:
            continue

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)[["티커", "신호", "점수", "RSI", "현재가", "20일선", "이유"]]
    return df_result.sort_values("점수", ascending=False).reset_index(drop=True)
