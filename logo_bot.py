import requests
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
import json
from datetime import datetime

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
# YARDIMCI FONKSİYON: TRADINGVIEW SCANNER (LOGO AVCISI)
# ==============================================================================
def get_tradingview_metadata(market):
    """
    TradingView'den hisse adını ve LOGO ID'sini çeker.
    market: 'turkey' (BIST) veya 'america' (ABD)
    """
    print(f"   -> {market.upper()} Logoları ve İsimleri Çekiliyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    # 'logoid' sütunu bize resmin adresini verecek
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"],
        "range": [0, 2000] # İlk 2000 hisse (Hepsini kapsar)
    }
    
    # TradingView Logo Sunucusu
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    
    data = {}
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=30)
        if r.status_code == 200:
            for h in r.json().get('data', []):
                d = h.get('d', [])
                # d[0]: Sembol (THYAO), d[1]: Tam İsim, d[2]: LogoID
                if len(d) > 2:
                    sembol = d[0]
                    isim = d[1]
                    logo_id = d[2]
                    
                    # Logo varsa linki oluştur, yoksa None
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    
                    data[sembol] = {"name": isim, "logo": logo_url}
    except Exception as e:
        print(f"   -> Hata: {e}")
    
    return data

# ==============================================================================
# VERİ TOPLAMA BAŞLIYOR
# ==============================================================================
print("--- PROFESYONEL LOGO BOTU BAŞLADI ---")

# 1. BIST (TRADINGVIEW)
meta_bist = get_tradingview_metadata("turkey")
print(f"   -> ✅ BIST: {len(meta_bist)} adet logo bulundu.")

# 2. ABD (TRADINGVIEW)
meta_abd = get_tradingview_metadata("america")
print(f"   -> ✅ ABD: {len(meta_abd)} adet logo bulundu.")

# 3. KRİPTO (COINMARKETCAP)
print("3. Kripto Logoları (CMC) Çekiliyor...")
meta_kripto = {}
if CMC_API_KEY:
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '300', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            for coin in r.json()['data']:
                sym = coin['symbol']
                # CMC Logo URL Yapısı (ID'ye göre)
                coin_id = coin['id']
                logo_url = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                
                meta_kripto[f"{sym}-USD"] = {
                    "name": coin['name'],
                    "logo": logo_url
                }
    except: pass
print(f"   -> ✅ Kripto: {len(meta_kripto)} adet logo bulundu.")

# 4. YATIRIM FONLARI (TEFAS)
print("4. Fon İsimleri Çekiliyor...")
meta_fon = {}
# Fonlar için standart, şık bir ikon
FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png" 

try:
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    date = datetime.now().strftime("%d.%m.%Y")
    payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": date, "bittarih": date}
    headers_tefas = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr", "Content-Type": "application/json"}
    
    s = requests.Session()
    s.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers_tefas) # Cookie
    r = s.post(url, json=payload, headers=headers_tefas)
    
    if r.status_code == 200:
        for f in r.json().get('data', []):
            meta_fon[f['FONKODU']] = {
                "name": f['FONADI'],
                "logo": FON_ICON
            }
except: pass
print(f"   -> ✅ Fon: {len(meta_fon)} adet isim bulundu.")

# 5. DÖVİZ (BAYRAKLAR)
print("5. Döviz Bayrakları Hazırlanıyor...")
meta_doviz = {}
# Manuel Eşleştirme Tablosu
bayraklar = {
    "USD": "us", "EUR": "eu", "GBP": "gb", "CHF": "ch", 
    "CAD": "ca", "JPY": "jp", "AUD": "au", "CNY": "cn",
    "DKK": "dk", "SEK": "se", "NOK": "no", "SAR": "sa"
}
isimler = {
    "USD": "ABD Doları", "EUR": "Euro", "GBP": "İngiliz Sterlini", "CHF": "İsviçre Frangı",
    "CAD": "Kanada Doları", "JPY": "Japon Yeni", "AUD": "Avustralya Doları",
    "EURUSD": "Euro / Dolar", "GBPUSD": "Sterlin / Dolar", "DX-Y": "Dolar Endeksi"
}

# Standart Listemiz
liste_doviz = ["USDTRY", "EURTRY", "GBPTRY", "CHFTRY", "CADTRY", "JPYTRY", "AUDTRY", "EURUSD", "GBPUSD", "DX-Y"]

for kur in liste_doviz:
    ana_kod = kur.replace("TRY", "").replace("=X", "")
    
    # Bayrak kodunu bul (USD -> us)
    flag_code = "un" # Bilinmeyen
    if ana_kod in bayraklar: flag_code = bayraklar[ana_kod]
    elif ana_kod == "EURUSD": flag_code = "eu"
    elif ana_kod == "GBPUSD": flag_code = "gb"
    elif ana_kod == "DX-Y": flag_code = "us"
    
    # İsim bul
    tam_isim = isimler.get(ana_kod, ana_kod)
    
    meta_doviz[kur] = {
        "name": tam_isim,
        "logo": f"https://flagcdn.com/w320/{flag_code}.png"
    }

# 6. ALTIN
print("6. Altın İkonları Hazırlanıyor...")
meta_altin = {}
GOLD_ICON = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"
SILVER_ICON = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png"

altinlar = ["Gram Altın", "Çeyrek Altın", "Yarım Altın", "Tam Altın", "Cumhuriyet A.", "Ata Altın", "Ons Altın", "22 Ayar Bilezik", "14 Ayar Altın", "18 Ayar Altın", "Gremse Altın", "Reşat Altın", "Hamit Altın", "Has Altın"]

for a in altinlar:
    meta_altin[a] = {"name": a, "logo": GOLD_ICON}
meta_altin["Gümüş"] = {"name": "Gümüş", "logo": SILVER_ICON}


# ==============================================================================
# BİRLEŞTİR VE KAYDET
# ==============================================================================
final_metadata = {
    "borsa_tr_tl": meta_bist,
    "borsa_abd_usd": meta_abd,
    "kripto_usd": meta_kripto,
    "fon_tl": meta_fon,
    "doviz_tl": meta_doviz,
    "altin_tl": meta_altin
}

print("Veritabanına gönderiliyor (system/assets_metadata)...")
doc
