import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta
import ta
from modules.us_stocks import TICKER_NAMES


def _flatten_yf(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def compute_signals(df: pd.DataFrame) -> dict:
    """기술적 지표 10가지 기반 매매 신호 (점수 범위: -14 ~ +14)

    지표 목록:
    1. RSI (14일)         - 과매도/과매수
    2. MACD               - 골든/데드크로스
    3. 볼린저 밴드        - 하단/상단 근접
    4. 스토캐스틱 %K      - 과매도/과매수
    5. 20일 이평선        - 추세 확인
    6. 60일 이평선        - 중기 추세
    7. 5일 이평선         - 단기 추세
    8. 120일 이평선       - 장기 추세
    9. 이평선 정배열      - 5>20>60>120
   10. 거래량 증가        - 20일 평균 대비
   11. ADX               - 추세 강도
   12. CCI               - 과매도/과매수
   13. Williams %R       - 과매도/과매수
   14. 52주 위치         - 저점/고점 근접
    """
    if df is None or len(df) < 30:
        return {}

    close = df["Close"] if "Close" in df.columns else df.get("종가")
    if close is None:
        return {}
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna().astype(float)
    if len(close) < 30:
        return {}

    high  = df.get("High",  df.get("고가",  close))
    low   = df.get("Low",   df.get("저가",  close))
    vol   = df.get("Volume", df.get("거래량", pd.Series([0]*len(close), index=close.index)))
    if isinstance(high, pd.DataFrame): high = high.iloc[:, 0]
    if isinstance(low,  pd.DataFrame): low  = low.iloc[:, 0]
    if isinstance(vol,  pd.DataFrame): vol  = vol.iloc[:, 0]
    high  = high.reindex(close.index).fillna(close).astype(float)
    low   = low.reindex(close.index).fillna(close).astype(float)
    vol   = vol.reindex(close.index).fillna(0).astype(float)

    score = 0
    reasons = []
    details = {}

    # 1. RSI (14일)
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    details["RSI"] = round(rsi, 1)
    if rsi < 30:
        score += 3; reasons.append(f"RSI 강한 과매도({rsi:.1f})")
    elif rsi < 40:
        score += 2; reasons.append(f"RSI 과매도({rsi:.1f})")
    elif rsi < 50:
        score += 1; reasons.append(f"RSI 중립하단({rsi:.1f})")
    elif rsi > 75:
        score -= 3; reasons.append(f"RSI 강한 과매수({rsi:.1f})")
    elif rsi > 65:
        score -= 2; reasons.append(f"RSI 과매수({rsi:.1f})")

    # 2. MACD
    macd_obj = ta.trend.MACD(close)
    macd_val = macd_obj.macd().iloc[-1]
    macd_sig = macd_obj.macd_signal().iloc[-1]
    macd_hist = macd_obj.macd_diff().iloc[-1]
    prev_hist = macd_obj.macd_diff().iloc[-2] if len(close) > 26 else macd_hist
    details["MACD"] = round(macd_val, 4)
    if macd_val > macd_sig:
        score += 2; reasons.append("MACD 골든크로스")
    else:
        score -= 1; reasons.append("MACD 데드크로스")
    if macd_hist > 0 and macd_hist > prev_hist:
        score += 1; reasons.append("MACD 히스토그램 상승")
    elif macd_hist < 0 and macd_hist < prev_hist:
        score -= 1; reasons.append("MACD 히스토그램 하락")

    # 3. 볼린저 밴드
    bb = ta.volatility.BollingerBands(close, window=20)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid   = bb.bollinger_mavg().iloc[-1]
    current  = close.iloc[-1]
    details["BB위치"] = f"{((current - bb_lower) / (bb_upper - bb_lower) * 100):.0f}%" if (bb_upper - bb_lower) > 0 else "N/A"
    if current <= bb_lower * 1.01:
        score += 2; reasons.append("볼린저 하단 근접(과매도)")
    elif current <= bb_lower * 1.03:
        score += 1; reasons.append("볼린저 하단 접근")
    elif current >= bb_upper * 0.99:
        score -= 2; reasons.append("볼린저 상단 근접(과매수)")
    elif current >= bb_upper * 0.97:
        score -= 1; reasons.append("볼린저 상단 접근")

    # 4. 스토캐스틱 %K
    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    stoch_k = stoch.stoch().iloc[-1]
    stoch_d = stoch.stoch_signal().iloc[-1]
    details["스토캐스틱"] = round(stoch_k, 1)
    if stoch_k < 20:
        score += 2; reasons.append(f"스토캐스틱 과매도({stoch_k:.1f})")
    elif stoch_k < 30:
        score += 1; reasons.append(f"스토캐스틱 저점권({stoch_k:.1f})")
    elif stoch_k > 80:
        score -= 2; reasons.append(f"스토캐스틱 과매수({stoch_k:.1f})")
    elif stoch_k > 70:
        score -= 1; reasons.append(f"스토캐스틱 고점권({stoch_k:.1f})")
    if stoch_k > stoch_d and stoch_k < 50:
        score += 1; reasons.append("스토캐스틱 골든크로스")

    # 5~8. 이동평균선 위치
    ma5   = close.rolling(5).mean().iloc[-1]   if len(close) >= 5   else current
    ma20  = close.rolling(20).mean().iloc[-1]  if len(close) >= 20  else current
    ma60  = close.rolling(min(60, len(close))).mean().iloc[-1]
    ma120 = close.rolling(min(120, len(close))).mean().iloc[-1]
    details["현재가"] = round(current, 2)
    details["20일선"] = round(ma20, 2)

    if current > ma5:   score += 1; reasons.append("5일선 위")
    else:               score -= 1
    if current > ma20:  score += 1; reasons.append("20일선 위")
    else:               score -= 1; reasons.append("20일선 아래")
    if current > ma60:  score += 1; reasons.append("60일선 위")
    else:               score -= 1
    if current > ma120: score += 1; reasons.append("120일선 위")
    else:               score -= 1

    # 9. 이동평균선 정배열 (5>20>60>120)
    if ma5 > ma20 > ma60 > ma120:
        score += 2; reasons.append("이평선 완전정배열")
    elif ma5 > ma20 > ma60:
        score += 1; reasons.append("이평선 부분정배열")
    elif ma5 < ma20 < ma60 < ma120:
        score -= 2; reasons.append("이평선 역배열")

    # 10. 거래량 분석
    vol_ma20 = vol.rolling(20).mean().iloc[-1]
    vol_today = vol.iloc[-1]
    if vol_ma20 > 0:
        vol_ratio = vol_today / vol_ma20
        if vol_ratio >= 2.0:
            score += 2; reasons.append(f"거래량 급증({vol_ratio:.1f}x)")
        elif vol_ratio >= 1.5:
            score += 1; reasons.append(f"거래량 증가({vol_ratio:.1f}x)")
        elif vol_ratio < 0.5:
            score -= 1; reasons.append("거래량 급감")

    # 11. ADX (추세 강도)
    try:
        adx_obj = ta.trend.ADXIndicator(high, low, close, window=14)
        adx_val = adx_obj.adx().iloc[-1]
        dip = adx_obj.adx_neg().iloc[-1]
        dim = adx_obj.adx_pos().iloc[-1]
        if adx_val > 25:
            if dim > dip:
                score += 1; reasons.append(f"ADX 상승추세({adx_val:.1f})")
            else:
                score -= 1; reasons.append(f"ADX 하락추세({adx_val:.1f})")
    except Exception:
        pass

    # 12. CCI (Commodity Channel Index)
    try:
        cci_val = ta.trend.CCIIndicator(high, low, close, window=20).cci().iloc[-1]
        if cci_val < -100:
            score += 1; reasons.append(f"CCI 과매도({cci_val:.0f})")
        elif cci_val > 100:
            score -= 1; reasons.append(f"CCI 과매수({cci_val:.0f})")
    except Exception:
        pass

    # 13. Williams %R
    try:
        wr = ta.momentum.WilliamsRIndicator(high, low, close, lbp=14).williams_r().iloc[-1]
        if wr < -80:
            score += 1; reasons.append(f"Williams %R 과매도({wr:.1f})")
        elif wr > -20:
            score -= 1; reasons.append(f"Williams %R 과매수({wr:.1f})")
    except Exception:
        pass

    # 14. 52주 고저 위치
    window_52 = min(252, len(close))
    high_52 = close.rolling(window_52).max().iloc[-1]
    low_52  = close.rolling(window_52).min().iloc[-1]
    if high_52 > low_52:
        pos_52 = (current - low_52) / (high_52 - low_52) * 100
        details["52주위치"] = f"{pos_52:.0f}%"
        if pos_52 < 15:
            score += 2; reasons.append(f"52주 저점 근접({pos_52:.0f}%)")
        elif pos_52 < 30:
            score += 1; reasons.append(f"52주 저점권({pos_52:.0f}%)")
        elif pos_52 > 90:
            score -= 2; reasons.append(f"52주 고점 근접({pos_52:.0f}%)")
        elif pos_52 > 75:
            score -= 1; reasons.append(f"52주 고점권({pos_52:.0f}%)")

    # 신호 등급 (점수 범위 확장됨)
    if score >= 10:
        signal, color = "강력 매수", "🟢"
    elif score >= 6:
        signal, color = "매수", "🔵"
    elif score <= -8:
        signal, color = "강력 매도", "🔴"
    elif score <= -4:
        signal, color = "매도", "🟠"
    else:
        signal, color = "관망", "⚪"

    return {
        "신호": f"{color} {signal}",
        "점수": score,
        "RSI": details.get("RSI"),
        "현재가": details.get("현재가"),
        "20일선": details.get("20일선"),
        "BB위치": details.get("BB위치"),
        "스토캐스틱": details.get("스토캐스틱"),
        "52주위치": details.get("52주위치"),
        "이유": " / ".join(reasons[:6]),  # 상위 6개만 표시
    }


def get_kr_recommendations(tickers: list, names: dict) -> pd.DataFrame:
    """한국 주식 추천 목록 (점수 4이상)"""
    results = []
    start = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    for ticker in tickers[:80]:
        try:
            df = fdr.DataReader(ticker, start)
            if df.empty or len(df) < 30:
                continue
            signals = compute_signals(df)
            if signals and signals["점수"] >= 1:
                signals["종목명"] = names.get(ticker, ticker)
                signals["티커"] = ticker
                results.append(signals)
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    cols = ["종목명", "티커", "신호", "점수", "RSI", "스토캐스틱", "BB위치", "52주위치", "현재가", "20일선", "이유"]
    df_result = pd.DataFrame(results)[[c for c in cols if c in pd.DataFrame(results).columns]]
    return df_result.sort_values("점수", ascending=False).reset_index(drop=True)


def get_us_recommendations(tickers: list) -> pd.DataFrame:
    """미국 주식 추천 목록 (배치 다운로드, 점수 4이상)"""
    watch_list = list(tickers[:50]) if tickers else [
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
        "AMD", "INTC", "NFLX", "PYPL", "UBER", "CRM", "ORCL", "ADBE",
        "COIN", "PLTR", "SOFI", "RIVN", "SHOP", "SNOW", "RBLX", "HOOD",
        "ABNB", "DASH", "LYFT", "SNAP", "PINS", "TWLO", "DDOG",
    ]

    try:
        data = yf.download(watch_list, period="9mo", auto_adjust=True, progress=False, group_by="ticker")
    except Exception:
        return pd.DataFrame()

    results = []
    for ticker in watch_list:
        try:
            if ticker in data.columns.get_level_values(0):
                df_ticker = data[ticker].copy()
            else:
                continue
            df_ticker = _flatten_yf(df_ticker).dropna(subset=["Close"])
            signals = compute_signals(df_ticker)
            if signals and signals["점수"] >= 1:
                signals["티커"] = ticker
                signals["회사명"] = TICKER_NAMES.get(ticker, ticker)
                results.append(signals)
        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    cols = ["티커", "회사명", "신호", "점수", "RSI", "스토캐스틱", "BB위치", "52주위치", "현재가", "20일선", "이유"]
    df_result = pd.DataFrame(results)[[c for c in cols if c in pd.DataFrame(results).columns]]
    return df_result.sort_values("점수", ascending=False).reset_index(drop=True)
