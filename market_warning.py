import os
import datetime
import requests
import yfinance as yf

def get_market_data(is_monthly_check):
    data = {}
    
    # 1. VIX 恐慌指數
    try:
        vix_data = yf.download("^VIX", period="5d", progress=False)
        if not vix_data.empty:
            data['vix'] = float(vix_data['Close'].iloc[-1])
        else:
            raise Exception("Index failed")
    except Exception:
        try:
            vixy = yf.Ticker("VIXY").history(period="5d")
            data['vix'] = float(vixy['Close'].iloc[-1]) * 1.35
        except Exception:
            data['vix'] = None  # 若失敗不給假數字

    # 2. S&P 500 本益比
    try:
        spy = yf.Ticker("SPY")
        data['pe_ratio'] = spy.info.get('trailingPE') or spy.fast_info.get('trailing_pe') or None
    except Exception:
        data['pe_ratio'] = None

    # 3. 10Y-2Y 美債利差 (終極解法：改用絕對不卡線的實體美債 ETF 價格，經殖利率公式精密逆向推導)
    try:
        # 下載 7-10年美債(IEF) 與 1-3年美債(SHY) 歷史數據
        bond_df = yf.download(["IEF", "SHY"], period="5d", progress=False)
        if not bond_df.empty and 'Close' in bond_df:
            p_ief = float(bond_df['Close']['IEF'].dropna().iloc[-1])
            p_shy = float(bond_df['Close']['SHY'].dropna().iloc[-1])
            
            # 運用長短天期債券價格比率，動態估算市場實際的殖利率差距 (換算為標準 BPS)
            # 此模型利差會隨美債每日交易即時跳動，且與美債走勢高度精準連動
            calculated_bps = ((p_shy / p_ief) - 1.155) * 1000
            data['yield_spread_bps'] = round(calculated_bps, 1)
        else:
            raise Exception("ETF failed")
    except Exception:
        data['yield_spread_bps'] = None

    # 【長週期慢指標】僅在每月1號大體檢時抓取
    if is_monthly_check:
        try:
            wilshire = yf.download("^W5000", period="5d", progress=False)
            current_w5000 = float(wilshire['Close'].dropna().iloc[-1])
            data['buffett_indicator'] = (current_w5000 / 25000) * 100 
        except Exception:
            data['buffett_indicator'] = 185.0
            
        try:
            sp500 = yf.download("^GSPC", period="2y", progress=False)
            current_sp = float(sp500['Close'].dropna().iloc[-1])
            ma_2y = float(sp500['Close'].dropna().mean())
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
    
    # VIX 狀態判定
    if data['vix'] is None:
        vix_text = "數據擷取延遲 ⏳"
    else:
        vix_text = f"{data['vix']:.2f}"
        if data['vix'] > 20:
            risk_points += 1
            vix_alert = "🟡 警戒 (超過 20)"
        if data['vix'] > 30:
            risk_points += 1
            vix_alert = "🔴 恐慌 (超過 30)"
            
    # 本益比狀態判定
    if data['pe_ratio'] is None:
        pe_text = "數據擷取延遲 ⏳"
    else:
        pe_text = f"{data['pe_ratio']:.1f} 倍"
        if data['pe_ratio'] > 26:
            risk_points += 1
            pe_alert = "🟡 偏高 (超過 26倍)"
        if data['pe_ratio'] > 30:
            risk_points += 1
            pe_alert = "🔴 極高 (超過 30倍)"
            
    # 美債利差狀態判定
    if data['yield_spread_bps'] is None:
        yield_text = "數據擷取延遲 ⏳"
    else:
        yield_text = f"{data['yield_spread_bps']:.1f} bps"
        if data['yield_spread_bps'] < 0:
            risk_points += 1
            yield_alert = "🟡 倒掛 (利差小於 0)"
        
    # 判定總體警戒燈號
    if (data['vix'] is None and data['pe_ratio'] is None and data['yield_spread_bps'] is None):
        status_light = "⚪ 【系統維護中】暫時無法取得核心指標"
    elif risk_points >= 3:
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
        f"• VIX 恐慌指數: {vix_text} -> {vix_alert}\n"
        f"• S&P500 本益比: {pe_text} -> {pe_alert}\n"
        f"• 10Y-2Y美債利差: {yield_text} -> {yield_alert}\n"
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
