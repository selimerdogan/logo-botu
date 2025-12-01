import requests
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
import json
from datetime import datetime, timedelta

# --- AYARLAR ---
headers_general = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# --- KİMLİK KONTROLLERİ ---
firebase_key_str = os.environ.get('FIREBASE_KEY')
CMC_API_KEY = os.environ.get('CMC_API_KEY')

if not firebase_key_str:
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    else:
        print("HATA: Anahtar yok!")
        sys.exit(1)
else:
    cred_dict = json.loads(firebase_key_str)
    cred = credentials.Certificate(cred_dict)

try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"HATA: Firebase hatası: {e}")
    sys.exit(1)

# ==============================================================================
# 1. BIST & ABD (TRADINGVIEW SCANNER - ORİJİNAL LOGOLAR VE UZUN İSİMLER)
# ==============================================================================
def get_tradingview_metadata(market):
    """
    TradingView'den hisse tam adını ve logo ID'sini çeker.
    market: 'turkey' veya 'america'
    """
    print(f"   -> {market.upper()} Logoları aranıyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    # Tüm hisseleri kapsayacak sorgu
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"],
        "range": [0, 4000] 
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=45)
        if r.status_code == 200:
            items = r.json().get('data', [])
            for h in items:
                d = h.get('d', [])
                if len(d) > 2:
                    sembol = d[0]
                    isim = d[1]   # Uzun İsim (Örn: Turk Hava Yollari)
                    logo_id = d[2]
                    
                    # Logo varsa link oluştur
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    
                    # İsim temizliği (varsa virgül sonrası gereksiz detayları at)
                    if "," in isim: isim = isim.split(",")[0]
                    
                    data[sembol] = {"name": isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet veri bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (CMC API - TOP 250 - UZUN İSİMLER)
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC API) çekiliyor...")
    
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC Key Yok! Statik liste kullanılacak.")
        # Yedek Statik Liste
        LISTE_YEDEK = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "TRX", "DOT", "LINK", "SHIB"]
        data = {}
        for c in LISTE_YEDEK:
            logo = f"https://assets.coincap.io/assets/icons/{c.lower()}@2x.png"
            data[f"{c}-USD"] = {"name": c, "logo": logo}
        return data

    # API ile Çekim
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '250', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    data = {}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            coins = r.json()['data']
            for coin in coins:
                sym = coin['symbol']
                name = coin['name'] # Bitcoin, Ethereum...
                coin_id = coin['id']
                
                # CMC Resmi Logo Sunucusu
                logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                
                data[f"{sym}-USD"] = {"name": name, "logo": logo}
            print(f"   -> ✅ CMC: {len(data)} adet kripto metadata alındı.")
    except Exception as e:
        print(f"   -> ⚠️ CMC Hatası: {e}")
        
    return data

# ==============================================================================
# 3. YATIRIM FONLARI (TEFAS - YEDEK LİSTE DESTEKLİ)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png"
    data = {}
    
    # --- A PLAN: YEDEK LİSTE (TEFAS Çökerse Diye) ---
    YEDEK_FONLAR = {
        "AFT": "Ak Portföy Yeni Teknolojiler", "TCD": "Tacirler Portföy Değişken", "MAC": "Marmara Capital Hisse",
        "YAY": "Yapı Kredi Yabancı Teknoloji", "IPJ": "İş Portföy Elektrikli Araçlar", "NNF": "Hedef Portföy Birinci",
        "TI2": "İş Portföy BIST Teknoloji", "AES": "Ak Portföy Petrol", "GMR": "Inveo Portföy Gümüş",
        "ADP": "Ak Portföy BIST 30", "IHK": "İş Portföy BIST 100 Dışı", "IDH": "İş Portföy BIST Temettü"
    }
    for kod, isim in YEDEK_FONLAR.items():
        data[kod] = {"name": isim, "logo": FON_ICON}

    # --- B PLAN: CANLI ÇEKİM (Geriye Dönük Tarama) ---
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.te
