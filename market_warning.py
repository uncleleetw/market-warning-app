import os
import requests
import yfinance as yf

def get_market_indicators():
    """自動抓取總經風控指標"""
    indicators = {"vix": None, "yield_spread": None, "spy_pe": None}
    try:
        # 1. 抓取 VIX 指數
        vix_ticker = yf.Ticker("^VIX")
        indicators["vix"] = float(vix_ticker.history(period="1d")['Close'].iloc[-1])
        
        # 2. 抓取長短債殖利率利差 (10年期美債 - 2年期美債)
        t10 = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1]
        t2 = yf.Ticker("^2YR").history(period="1d")['Close'].iloc[-1]
        indicators["yield_spread"] = float(t10 - t2)
        
        # 3. 抓取大盤估算本益比 P/E (以 SPY 為基準)
        spy = yf.Ticker("SPY")
        indicators["spy_pe"] = float(spy.info.get("trailingPE", 28.0))
    except Exception as e:
        print(f"部分總經指標抓取失敗: {e}")
    return indicators

def check_alarm_level(indicators):
    """計算三級警戒燈號邏輯"""
    vix = indicators["vix"]
    spread = indicators["yield_spread"]
    pe = indicators["spy_pe"]
    
    yellow_conditions = 0
    orange_conditions = 0
    
    # 🟡 黃燈判定條件
    if vix and vix > 25: yellow_conditions += 1
    if spread and 0 <= spread <= 0.2: yellow_conditions += 1
    if pe and pe > 35: yellow_conditions += 1
    
    # 🟠 橙燈判定條件 (含大盤高估替代方案)
    if vix and vix > 35: orange_conditions += 1
    if spread and spread < 0: orange_conditions += 1
    if pe and pe > 38: orange_conditions += 1 
    
    # 🔴 紅燈判定
    if (vix and vix > 45) or (orange_conditions >= 2):
        return ("🔴 紅燈（積極應對）\n"
                "⚠️ 警告：市場波動極度劇烈，或多項重度指標同時亮起！\n"
                "📣 提醒：請密切留意大型金融機構是否出現流動性危機之重大新聞。")
    
    # 🟠 橙燈
    if orange_conditions > 0 or yellow_conditions >= 3:
        return ("🟠 橙燈（提高防禦）\n"
                "💡 提示：防禦性指標已觸發！市場估值過高或利差倒掛，建議檢視現金流與防禦性資產配置。")
        
    # 🟡 黃燈
    if yellow_conditions > 0:
        return ("🟡 黃燈（留意市場波動）\n"
                "👀 提示：部分估值或利差指標進入警戒區，市場出現降溫或過熱前兆，維持冷靜觀察。")
        
    return "🟢 綠燈（安全無虞）\n✅ 狀態：市場各項總經與波動指標都在正常範圍，大盤環境健康。"

def send_line_message(access_token, user_id, message_text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": message_text}]
    }
    requests.post(url, headers=headers, json=payload)

def main():
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if not access_token or not user_id:
        print("錯誤: 找不到密鑰設定")
        return

    market_data = get_market_indicators()
    alarm_status = check_alarm_level(market_data)

    msg = f"🚨 全球大盤總經「三級警戒」觀測報告\n"
    msg += f"------------------------\n"
    msg += f"當前警戒狀態：\n{alarm_status}\n"
    msg += f"------------------------\n"
    
    if market_data["vix"] is not None:
        msg += f"📊 核心指標數據：\n"
        msg += f"• VIX 恐慌指數: {market_data['vix']:.2f} (黃>25, 橙>35, 紅>45)\n"
        msg += f"• 長短債殖利率差: {market_data['yield_spread']:.3f} (接近0為黃, 倒掛負值為橙)\n"
        msg += f"• 大盤粗估 P/E 比率: {market_data['spy_pe']:.1f} (高估>35為黃, 極端高估>38為橙)"

    send_line_message(access_token, user_id, msg)
    print("LINE 獨立風控通知發送成功！")

if __name__ == "__main__":
    main()
