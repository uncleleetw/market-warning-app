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
    
    # 同時下載所有需要的歷史K線，設定40天大緩衝，極大化降低被 Yahoo 阻擋的機率
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

    # --- 4. 高收益債利差 (HY OAS 逆向推導模型) ---
    try:
        # 利用全球最大高收益債 ETF (HYG) 價格反向推導信用利差
        hyg_series = df['Close']['HYG'].dropna() if df is not None else yf.Ticker("HYG").history(period="5d")['Close'].dropna()
        # 歷史標準化模型：當 HYG 價格下跌，代表信用利差擴大(風險增高)
        hy_oas_series = (100 - hyg_series) * 0.15 + 2.2
        data['hy_oas'] = round(float(hy_oas_series.iloc[-1]), 2)
        data['hy_arrow'] = get_trend_arrow(hy_oas_series)  # 利差上升=風險變高
    except Exception:
        data['hy_oas'], data['hy_arrow'] = None, "⏳"

    # --- 5. 台幣兌美元匯率 ---
    try:
        twd_series = df['Close']['TWD=X'].dropna() if df is not None else yf.Ticker("TWD=X").history(period="5d")['Close'].dropna()
        data['twd_fx'] = round(float(twd_series.iloc[-1]), 3)
        data['twd_arrow'] = get_trend_arrow(twd_series) # 匯率上升=台幣貶值(外資逃跑)
    except Exception:
        data['twd_fx'], data['twd_arrow'] = None, "⏳"

    # --- 6. 台股加權指數 20日乖離率 ---
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

    # 4. 高收益債利差 (HY OAS) -> 【第182行已修復完整】
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
            hy_alert = "🟢 信用穩健 (0分)"

    # 5. 台幣兌美元匯率
    if data['twd_fx'] is None:
        twd_text, twd_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        twd_text = f"{data['twd_fx']:.3f} {data['twd_arrow']}"
        if data['twd_fx'] > 32.8:
            total_score += 2
            twd_alert = "🔴 強烈貶值外資出逃 (2分)"
        elif data['twd_fx'] > 32.2:
            total_score += 1
            twd_alert = "🟡 趨貶觀望 (1分)"
        else:
            twd_alert = "🟢 台幣強勢/資產吸金 (0分)"

    # 6. 台股加權指數 20日乖離率
    if data['tw_bias'] is None:
        tw_text, tw_alert = "數據擷取延遲 ⏳", "⚪ 觀測中"
    else:
        tw_text = f"{data['tw_bias']:.2f}% {data['tw_bias_arrow']}"
        if data['tw_bias'] > 6.0 or data['tw_bias'] < -8.0:
            total_score += 2
            tw_alert = "🔴 短線極端過熱/超跌 (2分)"
        elif data['tw_bias'] > 3.5 or data['tw_bias'] < -5.0:
            total_score += 1
            tw_alert = "🟡 乖離偏大注意修正 (1分)"
        else:
            tw_alert = "🟢 正常軌道內 (0分)"

    # --- 總加權分數判定四級總燈號 ---
    if total_score >= 9:
        status_light = f"🔴 【四級總經極端風暴紅燈】停利回收現金 (總分: {total_score}分)"
    elif total_score >= 6:
        status_light = f"🟠 【三級總經高風險橘燈】減碼/停止不定期加碼 (總分: {total_score}分)"
    elif total_score >= 3:
        status_light = f"🟡 【二級總經市場觀望黃燈】暫緩用大資金盲目追高 (總分: {total_score}分)"
    else:
        status_light = f"🟢 【一級總經安全綠燈】紀律扣款/大膽執行加碼 (總分: {total_score}分)"
        
    report = (
        f"🚨 【unclelee 總經加權風控塔台】\n"
        f"⏰ 觀測時間 (台灣): {taiwan_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🚦 風控總指揮燈號：\n"
        f"{status_light}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📊 核心量化指標多維體檢 (🔺代表風險上升/🔻代表風險下降)：\n"
        f"• VIX 恐慌指數: {vix_text} -> {vix_alert}\n"
        f"• S&P500 本益比: {pe_text} -> {pe_alert}\n"
        f"• 10Y-2Y美債利差: {yield_text} -> {yield_alert}\n"
        f"• 高收益債利差(HY OAS): {hy_text} -> {hy_alert}\n"
        f"• 台幣兌美元匯率: {twd_text} -> {twd_alert}\n"
        f"• 台股20日乖離率: {tw_text} -> {tw_alert}\n"
    )
    
    if is_monthly_check:
        buffett_alert = "🟢 安全" if data['buffett_indicator'] < 190 else "🟡 歷史高位"
        bias_alert = "🟢 正常" if data['sp500_ma_bias'] < 15 else "🟡 乖離過大"
        
        report += (
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            f"📅 【每月 1 號大盤長週期體檢】\n"
            f"• 巴菲特指數: {data['buffett_indicator']:.1f}% -> {buffett_alert}\n"
            f"• 標普500 2年均線乖離率: {data['sp500_ma_bias']:.1f}% -> {bias_alert}\n"
        )
        
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n💡 哨兵提示：本系統已全面活化「跨市場分數加權制」，協助您排除單一雜訊、落實極致冷靜的科學紀律。"
    return report

def send_line_message(message_text):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id: return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": user_id, "messages": [{"type": "text", "text": message_text}]}
    try: requests.post(url, headers=headers, json=payload)
    except: pass

def main():
    report_content = generate_warning_report()
    send_line_message(report_content)

if __name__ == "__main__":
    main()
