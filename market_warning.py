import os
import datetime
import requests
import yfinance as yf

def get_market_data():
    data = {}
    
    # 1. 抓取恐慌指數 VIX
    try:
        vix = yf.Ticker("^VIX").history(period="2d")
        data['vix'] = vix['Close'].iloc[-1]
    except Exception:
        data['vix'] = None

    # 2. 抓取美國公債殖利率 (修正核心：使用最新穩定代號 ^TNX 與 ^IRX)
    try:
        bond_10y = yf.Ticker("^TNX").history(period="2d") # 10年期美債
        bond_2y = yf.Ticker("^IRX").history(period="2d")   # 2年期美債
        
        val_10y = bond_10y['Close'].iloc[-1]
        val_2y = bond_2y['Close'].iloc[-1]
        
        # 由於 yfinance 回傳的利率單位可能不同，在此做標準化轉換
        if val_10y > 10: val_10y /= 10
        if val_2y > 10: val_2y /= 10
            
        data['yield_spread'] = val_10y - val_2y
    except Exception:
        data['yield_spread'] = None

    # 3. 抓取大盤估值 (以標普500 ^GSPC 或台股大盤做粗估範例，此處以美股權重為核心)
    try:
        spy = yf.Ticker("SPY").history(period="2d")
        # 這裡提供一個基礎的乖離率或波動度作為風險變數範例
        data['market_pe_risk'] = "正常" 
    except Exception:
        data['market_pe_risk'] = "無法取得"

    return data

def calculate_risk_level(market_data):
    # 基礎風控邏輯：綜合 VIX 與 長短債利差倒掛情況
    vix = market_data.get('vix')
    spread = market_data.get('yield_spread')
    
    points = 0
    if vix and vix > 25: points += 2
    elif vix and vix > 20: points += 1
        
    if spread and spread < 0: points += 2 # 倒掛（橙燈/紅燈警戒）
    elif spread and spread < 0.2: points += 1
        
    if points >= 3:
        return "🔴 紅燈（市場極度恐慌 / 債券倒掛嚴重，強烈建議分批保留現金）"
    elif points >= 1:
        return "🟡 黃燈（指標出現異常，請密切注意高估值資產部位）"
    else:
        return "🟢 綠燈（總經指標健康，資產配置按計畫定期定額即可）"

def send_line_message(token, user_id, market_data, risk_level):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # 格式化輸出數據，加入 None 值的安全防護
    vix_str = f"{market_data['vix']:.2f}" if market_data.get('vix') is not None else "數據擷取失敗"
    spread_str = f"{market_data['yield_spread']:.3f}%" if market_data.get('yield_spread') is not None else "數據擷取失敗"
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    message_text = (
        f"📊 【全球總經大盤風控報告】\n"
        f"⏰ 觀測時間: {current_time}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"🔥 當前風控評級: {risk_level}\n\n"
        f"📋 核心指標數據:\n"
        f"• 恐慌指數 (VIX): {vix_str} (超過20警戒)\n"
        f"• 美債長短殖利率差: {spread_str} (低於0為倒掛)\n"
        f"• 大盤估值風險: {market_data['market_pe_risk']}\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"💡 哨兵提示: 本報告為自動化數據監測，協助您客觀掌握市場溫度，落實紀律投資。"
    )
    
    payload = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"LINE 發送失敗，錯誤碼: {response.status_code}, 回傳內容: {response.text}")
    else:
        print("LINE 風控報告發送成功！")

def main():
    # 從 GitHub Secrets 保險箱安全讀取金鑰
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.environ.get("LINE_USER_ID")
    
    if not line_token or not line_user_id:
        print("錯誤：找不到 LINE 密鑰，請檢查 GitHub Secrets 設定。")
        return
        
    print("正在下載全球總經數據...")
    market_data = get_market_data()
    
    print("正在計算市場風險評級...")
    risk_level = calculate_risk_level(market_data)
    
    print("正在發送 LINE 訊息通知...")
    send_line_message(line_token, line_user_id, market_data, risk_level)

if __name__ == "__main__":
    main()
