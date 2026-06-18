def get_market_data(is_monthly_check):
    data = {}
    
    # 1. VIX 恐慌指數
    try:
        vix_ticker = yf.Ticker("^VIX")
        vix_val = vix_ticker.fast_info.get('last_price') or vix_ticker.history(period="5d")['Close'].dropna().iloc[-1]
        data['vix'] = float(vix_val)
    except Exception:
        try:
            vixy_price = yf.Ticker("VIXY").fast_info.get('last_price') or yf.Ticker("VIXY").history(period="5d")['Close'].dropna().iloc[-1]
            data['vix'] = float(vixy_price) * 1.38
        except Exception:
            data['vix'] = None

    # 2. S&P 500 本益比
    try:
        spy = yf.Ticker("SPY")
        pe_val = spy.info.get('trailingPE') or spy.fast_info.get('trailing_pe') or spy.info.get('forwardPE')
        if pe_val and pe_val > 0:
            data['pe_ratio'] = float(pe_val)
        else:
            raise Exception("PE Empty")
    except Exception:
        try:
            sp500_price = yf.Ticker("^GSPC").fast_info.get('last_price') or yf.Ticker("^GSPC").history(period="5d")['Close'].dropna().iloc[-1]
            data['pe_ratio'] = round(float(sp500_price) / 238.5, 1)
        except Exception:
            data['pe_ratio'] = None

    # 3. 10Y-2Y 美債利差 (緩衝加強版：放寬至5天歷史)
    data['yield_spread_bps'] = None
    try:
        bond_df = yf.download(["^TNX", "^2Y"], period="5d", progress=False)
        if not bond_df.empty and 'Close' in bond_df:
            val_10y = float(bond_df['Close']['^TNX'].dropna().iloc[-1])
            val_2y = float(bond_df['Close']['^2Y'].dropna().iloc[-1])
            
            if val_10y > 15: val_10y /= 10
            if val_2y > 15: val_2y /= 10
            
            data['yield_spread_bps'] = round((val_10y - val_2y) * 100, 1)
    except Exception:
        try:
            t10 = yf.Ticker("^TNX").fast_info.get('last_price') or yf.Ticker("^TNX").history(period="5d")['Close'].dropna().iloc[-1]
            t02 = yf.Ticker("^2Y").fast_info.get('last_price') or yf.Ticker("^2Y").history(period="5d")['Close'].dropna().iloc[-1]
            if t10 and t02:
                if t10 > 15: t10 /= 10
                if t02 > 15: t02 /= 10
                data['yield_spread_bps'] = round((t10 - t02) * 100, 1)
        except Exception:
            data['yield_spread_bps'] = None
            
    return data
