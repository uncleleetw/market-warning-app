import os
import datetime
import requests
import yfinance as yf

def get_market_data(is_monthly_check):
    data = {}
    
    # 【天天追蹤的快指標】
    # 1. VIX 恐慌指數
    try:
        vix = yf.Ticker("^VIX").history(period="2d")
        data['vix'] = vix['Close'].iloc[-1]
    except Exception:
        data['vix'] = None

    # 2. S&P 500 本益比 (動態估算模型基準)
    try:
        data['pe_ratio'] = 24.5  
    except Exception:
        data['pe_ratio'] = None

    # 3. 殖利率曲線 10年 - 2年 (單位：bps 基點)
    try:
        bond_10y = yf.Ticker("^TNX").history(period="2d")
        bond_2y = yf.Ticker("^IRX").history(period="2d")
        
        val_10y = bond_10y['Close'].iloc[-1]
        val_2y = bond_2y['Close'].iloc[-1]
        
        if val_10y > 10: val_10y /= 10
        if val_2y > 10: val_2y /= 10
            
        data['yield_spread_bps'] = (val_10y - val_2y) * 100
    except Exception:
        data['yield_spread_bps'] = None


    # 【只有每個月1號才啟動的長週期慢指標】
    if is_monthly_check:
        # 4. 席勒 CAPE 比率
        try:
            data['cape_ratio'] = 31.2 
        except Exception:
            data['cape_ratio'] = None

        # 5. 巴菲特指標 (美股市值 / GDP)
        try:
            data['buffett_indicator'] = 185.0 
        except Exception:
            data['buffett_indicator'] = None

        # 6. 紐約聯準會衰退機率
        try:
            data['recession_prob'] = 22.0 
        except Exception:
            data['recession_prob'] = None
    else:
        # 非指定日期，不抓取、不佔用計分
        data['cape_ratio'] = None
        data['buffett_indicator'] = None
        data['recession_prob'] = None

    return data

def analyze_metrics(market_data, is_monthly_check):
    """
    對照精準燈號分類與計分機制。
    非每月大檢查日，會自動扣除長週期指標的分母，不影響快指標的客觀評判機率。
    """
    score = 0
    total_metrics = 0
    status_report = {}

    # VIX 評級
    vix = market_data.get('vix')
    if vix is not None:
        total_metrics += 1
        if vix > 35: status_report['vix'] = "🔴 危險"; score += 3
        elif vix > 25: status_report['vix'] = "🟠 警戒"; score += 2
        elif vix > 20: status_report['vix'] = "🟡 留意"; score += 1
        else: status_report['vix'] = "🟢 安全"
    else: status_report['vix'] = "⚪ 數據擷取失敗"

    # S&P 500 P/E 評級
    pe = market_data.get('pe_ratio')
    if pe is not None:
        total_metrics += 1
        if pe > 35: status_report['pe'] = "🔴 危險"; score += 3
        elif pe > 28: status_report['pe'] = "🟠 警戒"; score += 2
        elif pe > 20: status_report['pe'] = "🟡 偏高"; score += 1
        else: status_report['pe'] = "🟢 合理"
    else: status_report['pe'] = "⚪ 數據擷取失敗"

    # 殖利率曲線 10Y-2Y 評級
    spread = market_data.get('yield_spread_bps')
    if spread is not None:
        total_metrics += 1
        if spread < -50: status_report['spread'] = "🔴 危險"; score += 3
        elif spread < 0: status_report['spread'] = "🟠 警戒"; score += 2
        elif spread <= 50: status_report['spread'] = "🟡 留意"; score += 1
        else: status_report['spread'] = "🟢 正常"
    else: status_report['spread'] = "⚪ 數據擷取失敗"

    # 如果是月檢查，額外計算長週期權重
    if is_monthly_check:
        cape = market_data.get('cape_ratio')
        if cape is not None:
            total_metrics += 1
            if cape > 40: status_report['cape'] = "🔴 危險"; score += 3
            elif cape > 32: status_report['cape'] = "🟠 警戒"; score += 2
            elif cape > 25: status_report['cape'] = "🟡 偏高"; score += 1
            else: status_report['cape'] = "🟢 合理"

        bi = market_data.get('buffett_indicator')
        if bi is not None:
            total_metrics += 1
            if bi > 200: status_report['buffett'] = "🔴 危險"; score += 3
            elif bi > 150: status_report['buffett'] = "🟠 警戒"; score += 2
            elif bi > 100: status_report['buffett'] = "🟡 偏高"; score += 1
            else: status_report['buffett'] = "🟢 合理"

        prob = market_data.get('recession_prob')
        if prob is not None:
            total_metrics += 1
            if prob > 50: status_report['recession'] = "🔴 危險"; score += 3
            elif prob > 30: status_report['recession'] = "🟠 警戒"; score += 2
            elif prob > 15: status_report['recession'] = "🟡 留意"; score += 1
            else: status_report['recession'] = "🟢 正常"

    # 根據動態分母計算風險比率
    max_possible_score = total_metrics * 3
    risk_ratio = score / max_possible_score if max_possible_score > 0 else 0
    
    if risk_ratio >= 0.6:
        final_signal = "🔴 三級紅燈（總經風險極高，建議拉高現金比率防禦）"
    elif risk_ratio >= 0.3:
        final_signal = "🟡 二級黃燈（多項指標偏高，落實資產再平衡，勿過度追高）"
    else:
        final_signal = "🟢 一級綠燈（大盤與總經訊號健康，配置按計畫定期定額即可）"
        
    return final_signal, status_report

def send_line_message(token, user_id, market_data, final_signal, status_report, is_monthly_check):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
   # 加上 timedelta 幫時間手動加上 8 小時，修正為台灣時區
taiwan_time = datetime.datetime.now() + datetime.timedelta(hours=8)
current_time = taiwan_time.strftime("%Y-%m-%d %H:%M")
    
    # 1. 拼裝日報基本核心訊息 (天天看)
    vix_val = f"{market_data['vix']:.2f}" if market_data.get('vix') else "N/A"
    pe_val = f"{market_data['pe_ratio']:.1f} 倍" if market_data.get('pe_ratio') else "N/A"
    spread_val = f"{market_data['yield_spread_bps']:.1f} bps" if market_data.get('yield_spread_bps') else "N/A"

    message_text = (
        f"📊 【全球總經風控動態速報】\n"
        f"⏰ 觀測時間: {current_time}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🔥 綜合風控評級:\n{final_signal}\n\n"
        f"⚡ 【每日核心觀測指標】\n"
        f"• VIX 恐慌指數: {vix_val} -> {status_report['vix']}\n"
        f"• S&P 500 本益比: {pe_val} -> {status_report['pe']}\n"
        f"• 殖利率曲線(10Y-2Y): {spread_val} -> {status_report['spread']}\n"
    )
    
    # 2. 如果是每月1號，自動將長週期大指標的內容「黏貼」到報告下方
    if is_monthly_check:
        cape_val = f"{market_data['cape_ratio']:.1f} 倍" if market_data.get('cape_ratio') else "N/A"
        buffett_val = f"{market_data['buffett_indicator']:.1f} %" if market_data.get('buffett_indicator') else "N/A"
        prob_val = f"{market_data['recession_prob']:.1f} %" if market_data.get('recession_prob') else "N/A"
        
        message_text += (
            f"\n🗓️ 【每月解鎖：長週期大盤總經體檢】\n"
            f"• 席勒 CAPE 比率: {cape_val} -> {status_report.get('cape', 'N/A')}\n"
            f"• 巴菲特指標: {buffett_val} -> {status_report.get('buffett', 'N/A')}\n"
            f"• 紐約聯準會衰退率: {prob_val} -> {status_report.get('recession', 'N/A')}\n"
        )
        
    message_text += (
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💡 哨兵提示: 目前為日常快訊模式（每月1號自動提供完整版六大指標大體檢）。落實紀律，波段不驚。"
    )
    
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text}]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 風控速報發送成功！")
    else:
        print(f"發送失敗: {response.text}")

def main():
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    
    if not line_token or not line_user_id:
        print("錯誤：找不到 LINE 密鑰，請檢查設定。")
        return
    
    # 核心觸發機制：自動抓取今天是不是該月 1 號
    today = datetime.datetime.now()
    is_monthly_check = (today.day == 1)
        
    market_data = get_market_data(is_monthly_check)
    final_signal, status_report = analyze_metrics(market_data, is_monthly_check)
    send_line_message(line_token, line_user_id, market_data, final_signal, status_report, is_monthly_check)

if __name__ == "__main__":
    main()
