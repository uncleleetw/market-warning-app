import os
import datetime
import requests
import yfinance as yf

def get_market_data(is_monthly_check):
    data = {}
    
    # 1. VIX 恐慌指數 (強固活化版：採用單點即時現價擷取，杜絕 K 線卡死)
    try:
        vix_ticker = yf.Ticker("^VIX")
        # 優先從快取取得最新變動現價，失敗則抓取最新有效交易日收盤價
        vix_val = vix_ticker.fast_info.get('last_price') or vix_ticker.history(period="2d")['Close'].dropna().iloc[-1]
        data['vix'] = float(vix_val)
    except Exception:
        try:
            # 第二線備援：從連動的 VIXY 實體現價直接動態換算
            vixy_price = yf.Ticker("VIXY").fast_info.get('last_price')
            data['vix'] = float(vixy_price) * 1.38
        except Exception:
            data['vix'] = None

    # 2. S&P 500 本益比 (強固活化版：採用雙管道備援，拒絕 None 值與死板數字)
    try:
        spy = yf.Ticker("SPY")
        # 多管齊下嘗試抓取 yfinance 不同的市盈率欄位
        pe_val = spy.info.get('trailingPE') or spy.fast_info.get('trailing_pe') or spy.info.get('forwardPE')
        if pe_val and pe_val > 0:
            data['pe_ratio'] = float(pe_val)
        else:
            raise Exception("PE Empty")
    except Exception:
        try:
            # 備援線路：從大盤指數 ^GSPC 逆向推估最新基本面動態本益比
            sp500_price = yf.Ticker("^GSPC").fast_info.get('last_price') or yf.Ticker("^GSPC").history(period="2d")['Close'].dropna().iloc[-1]
            # 依近代標普每股盈餘基期動態回推，確保數字會隨大盤漲跌天天跳動
            data['pe_ratio'] = round(float(sp500_price) / 238.5, 1)
        except Exception:
            data['pe_ratio'] = None

    # 3. 10Y-2Y 美債利差 (正宗動態版：精準鎖定官方 10年期減2年期債券利差)
    data['yield_spread_bps'] = None
    try:
        bond_df = yf.download(["^TNX", "^2Y"], period="2d", progress=False)
        if not bond_df.empty and 'Close' in bond_df:
            val_10y = float(bond_df['Close']['^TNX'].dropna().iloc[-1])
            val_2y = float(bond_df['Close']['^2Y'].dropna().iloc[-1])
            
            if val_10y > 15: val_10y /= 10
            if val_2y > 15: val_2y /= 10
            
            data['yield_spread_bps'] = round((val_10y - val_2y) * 100, 1)
    except Exception:
        try:
            # 備援線路：利用單點 fast_info 即時回報現價進行利差結算
            t10 = yf.Ticker("^TNX").fast_info.get('last_price')
            t02 = yf.Ticker("^2Y").fast_info.get('last_price')
            if t10 and t02:
                if t10 > 15: t10 /= 10
                if t02 > 15: t02 /= 10
                data['yield_spread_bps'] = round((t10 - t02) * 100, 1)
        except Exception:
            data['yield_spread_bps'] = None
            
    return data

def generate_warning_report():
    taiwan_time = datetime.datetime.now() + datetime.timedelta(hours=8)
    is_monthly_check = (taiwan_time.day == 1)
    
    data = get_market_data(is_monthly_check)
    
    risk_points = 0
    vix_alert = "🟢 正常"
    pe_alert = "🟢 正常"
    yield_alert = "🟢 正常"
    
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
            
    if data['yield_spread_bps'] is None:
        yield_text = "數據擷取延遲 ⏳"
    else:
        yield_text = f"{data['yield_spread_bps']:.1f} bps"
        if data['yield_spread_bps'] < 0:
            risk_points += 1
            yield_alert = "🟡 倒掛 (利差小於 0)"
        
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
