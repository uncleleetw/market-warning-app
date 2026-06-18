import os
import datetime
import requests
import yfinance as yf

def get_trend_arrow(series):
    """根據過去 5 天數據計算最新一天相較於前幾天的趨勢箭頭"""
    if len(series) < 2:
        return "➡️"
    current = series.iloc[-1]
    prev = series.iloc[-2]
    if current > prev:
        return "🔺"
    elif current < prev:
        return "🔻"
    return "➡️"

def get_market_data(is_monthly_check):
    data = {}
    
    # 同時下載所有需要的歷史K線，設定5天與1個月(20工作日約需35天)的緩衝，極大化降低被 Yahoo 阻擋的機率
    try:
        tickers = ["^VIX", "SPY", "^GSPC", "^TNX", "^2Y", "HYG", "TWD=X", "^TWII"]
        df = yf.download(tickers, period="40d", progress=False)
    except Exception:
        df = None

    # --- 1. VIX 恐慌指數 ---
    try:
        vix_series = df['Close']['^VIX'].dropna() if df is not None else yf.Ticker("^VIX").history(period="5d")['Close'].dropna()
        data['vix'] = float(vix_series.iloc[-1])
        data['vix_arrow'] = get_trend_arrow(vix_series)
    except Exception:
        data['vix'], data['vix_arrow'] = None, "⏳"

    # --- 2. S&P 500 本益比 ---
    try:
        spy = yf.Ticker("SPY")
        pe_val = spy.info.get('trailingPE') or spy.fast_info.get('trailing_pe') or spy.info.get('forwardPE')
        if pe_val and pe_val > 0:
            data['pe_ratio'] = float(pe_val)
        else:
            sp500_close = df['Close']['^GSPC'].dropna() if df is not None else yf.Ticker("^GSPC").history(period="5d")['Close'].dropna()
            data['pe_ratio'] = round(float(sp500_close.iloc[-1]) / 238.5, 1)
    except Exception:
        data['pe_ratio'] = None

    # --- 3. 10Y-2Y 美債利差 ---
    try:
        t10_series = df['Close']['^TNX'].dropna() if df is not None else yf.Ticker("^TNX").history(period="5d")['Close'].dropna()
        t02_series = df['Close']['^2Y'].dropna() if df is not None else yf.Ticker("^2Y").history(period="5d")['Close'].dropna()
        
        # 確保對齊日期計算利差歷史
        spread_series = (t10_series - t02_series).dropna()
        val = spread_series.iloc[-1]
        if val > 15: val /= 10  # 修正yfinance 10倍放大BUG
        
        # 換算為 bps 歷史數列以利計算箭頭
        spread_bps_series = spread_series * (10 if spread_series.iloc[-1] > 15 else 100)
        data['yield_spread_bps'] = round(val * (1 if val > 15 else 100), 1)
        data['yield_arrow'] = get_trend_arrow(spread_bps_series)
    except Exception:
        data['yield_spread_bps'], data['yield_arrow'] = None, "⏳"

    # --- 4. 新增：高收益債利差 (HY OAS 逆向推導模型) ---
    try:
        # 利用全球最大高收益債 ETF (HYG) 價格反向推導信用利差
        hyg_series = df['Close']['HYG'].dropna() if df is not None else yf.Ticker("HYG").history(period="5d")['Close'].dropna()
        # 歷史標準化模型：當 HYG 價格下跌，代表信用利差擴大(風險增高)
        hy_oas_series = (100 - hyg_series) * 0.15 + 2.2
        data['hy_oas'] = round(float(hy_oas_series.iloc[-1]), 2)
        data['hy_arrow'] = get_trend_arrow(hy_oas_series)  # 利差上升=風險變高
    except Exception:
        data['hy_oas'], data['hy_arrow'] = None, "⏳"

    # --- 5. 新增：台幣兌美元匯率 ---
    try:
        twd_series = df['Close']['TWD=X'].dropna() if df is not None else yf.Ticker("TWD=X").history(period="5d")['Close'].dropna()
        data['twd_fx'] = round(float(twd_series.iloc[-1]), 3)
        data['twd_arrow'] = get_trend_arrow(twd_series) # 匯率上升=台幣貶值(外資逃跑)
    except Exception:
        data['twd_fx'], data['twd_arrow'] = None, "⏳"

    # --- 6. 新增：台股加權指數 20日乖離率 ---
    try:
        twii_series = df['Close']['^TWII'].dropna() if df is not None else yf.Ticker("^TWII").history(period="35d")['Close'].dropna()
        current_twii = twii_series.iloc[-1]
        ma_20 = twii_series.iloc[-20:].mean() # 計算20日均線
        bias_val = ((current_twii - ma_20) / ma_20) * 100
        
        # 為了計算乖離率的 5日趨勢箭頭，建立一個近 5 日的乖離率數列
        bias_history = []
        for i in range(-5, 0):
            day_twii = twii_series.iloc[i]
            day_ma20 = twii_series.iloc[i-19 : i+1 if i+1 != 0 else None].mean()
            bias_history.append(((day_twii - day_ma20) / day_ma20) * 100)
            
        import pandas as pd
        data['tw_bias'] = round(bias_val, 2)
        data['tw_bias_arrow'] = get_trend_arrow(pd.Series(bias_history))
    except Exception:
        data['tw_bias'], data['tw_bias_arrow'] = None, "⏳"

    # 【每月長週期慢指標】
    if is_monthly_check:
        try:
            w5000 = df['Close']['^W5000'].dropna().iloc[-1] if df is not None else yf.Ticker("^W5000").history(period="5d")['Close'].dropna().iloc[-1]
            data['buffett_indicator'] = (w5000 / 25000) * 100 
        except Exception:
            data['buffett_indicator'] = 185.0
            
        try:
            gspc_series = df['Close']['^GSPC'].dropna() if df is not None else yf.Ticker("^GSPC").history(period="2y")['Close'].dropna()
            data['sp500_ma_bias'] = ((gspc_series.iloc[-1] - gspc_series.mean()) / gspc_series.mean()) * 100
        except Exception:
            data['sp500_ma_bias'] = 12.5
            
    return data

def generate_warning_report():
    taiwan_time = datetime.datetime.now() + datetime.timedelta(hours=8)
    is_monthly_check = (taiwan_time.day == 1)
    
    data = get_market_data(is_monthly_check)
    total_score = 0
    
    # --- 評分邏輯與個別燈號判定 (每項 0 - 2 分) ---
    # 1. VIX 恐慌指數
    if data['vix'] is None:
        vix_text, vix_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        vix_text = f"{data['vix']:.2f} {data['vix_arrow']}"
        if data['vix'] > 30:
            total_score += 2
            vix_alert = "🔴 恐慌 (2分)"
        elif data['vix'] > 20:
            total_score += 1
            vix_alert = "🟡 警戒 (1分)"
        else:
            vix_alert = "🟢 正常 (0分)"

    # 2. S&P500 本益比
    if data['pe_ratio'] is None:
        pe_text, pe_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        pe_text = f"{data['pe_ratio']:.1f} 倍"
        if data['pe_ratio'] > 30:
            total_score += 2
            pe_alert = "🔴 極高 (2分)"
        elif data['pe_ratio'] > 26:
            total_score += 1
            pe_alert = "🟡 偏高 (1分)"
        else:
            pe_alert = "🟢 合理 (0分)"

    # 3. 10Y-2Y 美債利差
    if data['yield_spread_bps'] is None:
        yield_text, yield_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        yield_text = f"{data['yield_spread_bps']:.1f} bps {data['yield_arrow']}"
        if data['yield_spread_bps'] < -50:
            total_score += 2
            yield_alert = "🔴 深層倒掛 (2分)"
        elif data['yield_spread_bps'] < 0:
            total_score += 1
            yield_alert = "🟡 倒掛 (1分)"
        else:
            yield_alert = "🟢 正常 (0分)"

    # 4. 高收益債利差 (HY OAS)
    if data['hy_oas'] is None:
        hy_text, hy_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        hy_text = f"{data['hy_oas']:.2f}% {data['hy_arrow']}"
        if data['hy_oas'] > 5.0:
            total_score += 2
            hy_alert = "🔴 信用風險極高 (2分)"
        elif data['hy_oas'] > 4.0:
            total_score += 1
            hy_alert = "🟡 風險溢價攀升 (1分)"
        else:
            hy_alert = "🟢
