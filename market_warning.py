import os
import datetime
import requests
import yfinance as yf

def get_market_data(is_monthly_check):
    data = {}
    
    # 1. VIX 恐慌指數 (修正版：直接強制抓取最新一個有效交易日的歷史收盤價，確保不卡死在舊數據)
    try:
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="3d")
        if not vix_hist.empty:
            data['vix'] = float(vix_hist['Close'].iloc[-1])
        else:
            data['vix'] = 17.68
    except Exception:
        data['vix'] = 17.68  # 斷線時的安全備援值

    # 2. S&P 500 本益比 (從 SPY ETF 動態抓取實時市盈率)
    try:
        spy = yf.Ticker("SPY")
        data['pe_ratio'] = spy.info.get('trailingPE') or spy.fast_info.get('trailing_pe') or 27.0
    except Exception:
        data['pe_ratio'] = 27.0  # 斷線時的安全備援值

    # 3. 殖利率曲線 10年 - 2年 (動態即時計算利差 bps)
    try:
        bond_10y_ticker = yf.Ticker("^TNX")
        bond_2y_ticker = yf.Ticker("^IRX")
        
        # 強制抓歷史收盤數據，避免 fast_info 在非交易時段回傳卡住的舊值
        hist_10y = bond_10y_ticker.history(period="3d")
        hist_2y = bond_2y_ticker.history(period="3d")
        
        val_10y = hist_10y['Close'].iloc[-1]
        val_2y = hist_2y['Close'].iloc[-1]
        
        # 修正 yfinance 對債券殖利率可能放大 10 倍的極端回傳問題
        if val_10y > 15: val_10y /= 10
        if val_2y > 15: val_2y /= 10
            
        data['yield_spread_bps'] = (val_10y - val_2y) * 100
    except Exception:
        data['yield_spread_bps'] = 86.9  # 斷線時的安全備援值

    # 【長週期慢指標】僅在每月1號大體檢時抓取
    if is_monthly_check:
        try:
            wilshire = yf.Ticker("^W5000")
            current_w5000 = wilshire.history(period="2d")['Close'].iloc[-1]
            data['buffett_indicator'] = (current_w5000 / 25000) * 100 
        except Exception:
            data['buffett_indicator'] = 185.0
            
        try:
            sp500 = yf.Ticker("^GSPC")
            hist_2y = sp500.history(period="2y")
            current_sp = hist_2y['Close'].iloc[-1]
            ma_2y = hist_2y['Close'].mean()
            data['sp500_ma_bias'] = ((current_sp - ma_2y) / ma_2y) * 100
        except Exception:
            data['sp500_ma_bias'] = 12.5
            
    return data

def generate_warning_report():
    taiwan_time = datetime.datetime.now() + datetime.timedelta(hours=8)
    is_monthly_check = (taiwan_time.day == 1)
    
    data = get_market_data(is_monthly_check)
    
    risk_points = 0
    vix_alert = "🟢 正常"
    pe_alert = "🟢 正常"
    yield_alert = "🟢 正常"
    
    if data['vix'] > 20:
        risk_points += 1
        vix_alert = "🟡 警戒 (超過 20)"
    if data['vix'] > 30:
        risk_points += 1
        vix_alert = "🔴 恐慌 (超過 30)"
        
    if data['pe_ratio'] > 26:
        risk_points += 1
        pe_alert = "🟡 偏高 (超過 26倍)"
    if data['pe_ratio'] > 30:
        risk_points += 1
        pe_alert = "🔴 極高 (超過 30倍)"
        
    if data['yield_spread_bps'] < 0:
        risk_points += 1
        yield_alert = "🟡 倒掛 (利差小於 0)"
        
    if risk_points >= 3:
        status_light = "🔴 【三級總經高風險警戒】減碼/停止扣款"
    elif risk_points >= 1:
        status_light = "🟡 【二級總經市場觀望】暫緩加碼"
    else:
        status_light = "🟢 【一級總經安全綠燈】紀律投資/加碼"
        
    report = (
        f"🚨 【unclelee 總經風控指標提醒】\n"
        f"⏰ 觀測時間 (台灣): {taiwan_time.strftime('%Y-%m-%d %H:%M')}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🚦 當前風控總燈號：\n"
        f"{status_light}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"📊 核心快指標觀測：\n"
        f"• VIX 恐慌指數: {data['vix']:.2f} -> {vix_alert}\n"
        f"• S&P500 本益比: {data['pe_ratio']:.1f} 倍 -> {pe_alert}\n"
        f"• 10Y-2Y美債利差: {data['yield_spread_bps']:.1f} bps -> {yield_alert}\n"
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
        
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n💡 哨兵提示：本指標每日自動追蹤全球三大核心數據，協助您冷靜對抗市場情緒。"
    return report

def send_line_message(message_text):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if not token or not user_id:
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text}]
    }
    try:
        requests.post(url, headers=headers, json=payload)
    except Exception:
        pass

def main():
    report_content = generate_warning_report()
    send_line_message(report_content)

if __name__ == "__main__":
    main()
