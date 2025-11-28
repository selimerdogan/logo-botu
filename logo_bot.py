import requests
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
import json
import io
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
# DATA TOPLAYICILAR
# ==============================================================================

# 1. BIST İSİMLERİ VE LOGOLARI (TRADINGVIEW ORİJİNAL)
def get_bist_metadata():
    print("1. BIST Logo ve İsimleri çekiliyor (TradingView)...")
    url = "https://scanner.tradingview.com/turkey/scan"
    
    # TradingView'den 'logoid' verisini de istiyoruz
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"], # logoid ekledik
        "range": [0, 1000]
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    
    try:
        r = requests.post(url, json=payload, headers=headers_general)
        for h in r.json().get('data', []):
            d = h.get('d', []) # [Sembol, İsim, LogoID]
            if len(d) > 2:
                sembol = d[0]
                isim = d[1]
                logo_id = d[2]
                
                # Eğer TradingView'de logosu varsa onu kullan, yoksa boş bırak (aşağıda avatar atanır)
                if logo_id:
                    logo_link = f"{base_logo_url}{logo_id}.svg"
                else:
                    logo_link = None
                    
                data[sembol] = {"name": isim, "logo": logo_link}
    except Exception as e:
        print(f"BIST Hata: {e}")
        
    return data

# 2. ABD İSİMLERİ (GITHUB CSV - YAHOO UYUMLU)
def get_abd_metadata():
    print("2. ABD İsimleri çekiliyor...")
    # ABD hisseleri için logo bulmak zordur, şimdilik Avatar devam.
    # İleride Clearbit API eklenebilir.
    import pandas as pd # Local import
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
    data = {}
    try:
        s = requests.get(url).content
        df = pd.read_csv(io.StringIO(s.decode('utf-8')))
        for index, row in df.iterrows():
            sym = row['Symbol'].replace('.', '-')
            name = row['Security']
            data[sym] = name
    except: pass
    return data

# 3. KRİPTO İSİMLERİ (CMC)
def get_kripto_metadata():
    print("3. Kripto İsimleri çekiliyor...")
    if not CMC_API_KEY: return {}
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '300', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    data = {}
    try:
        r = requests.get(url, headers=headers, params=params)
        for coin in r.json()['data']:
            sym = f"{coin['symbol']}-USD"
            name = coin['name']
            data[sym] = name
    except: pass
    return data

# 4. FON İSİMLERİ (TEFAS)
def get_fon_metadata():
    print("4. Fon İsimleri çekiliyor...")
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    date = datetime.now().strftime("%d.%m.%Y")
    payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": date, "bittarih": date}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.tefas.gov.tr/FonKarsilastirma.aspx",
        "Origin": "https://www.tefas.gov.tr", 
        "Content-Type": "application/json; charset=UTF-8"
    }
    data = {}
    try:
        s = requests.Session()
        try: s.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers, timeout=10)
        except: pass
        
        r = s.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            for f in r.json().get('data', []):
                data[f['FONKODU']] = f['FONADI']
    except: pass
    return data

# ==============================================================================
# ANA İŞLEM VE BİRLEŞTİRME
# ==============================================================================

# Verileri Çek
meta_bist = get_bist_metadata()
meta_abd = get_abd_metadata()
meta_kripto = get_kripto_metadata()
meta_fon = get_fon_metadata()

# Manuel Tanımlar
meta_doviz = {
    "USD": "ABD Doları", "EUR": "Euro", "GBP": "İngiliz Sterlini", "CHF": "İsviçre Frangı",
    "CAD": "Kanada Doları", "JPY": "Japon Yeni", "AUD": "Avustralya Doları", "CNY": "Çin Yuanı",
    "EURUSD": "Euro / Dolar", "GBPUSD": "Sterlin / Dolar", "DX-Y": "Dolar Endeksi"
}
meta_altin = {
    "Gram Altın": "24 Ayar Gram", "Çeyrek Altın": "Çeyrek Altın", "Yarım Altın": "Yarım Altın",
    "Tam Altın": "Tam Altın", "Cumhuriyet A.": "Cumhuriyet Altını", "Ata Altın": "Ata Lira",
    "Ons Altın": "Uluslararası Ons", "22 Ayar Bilezik": "22 Ayar Bilezik", "14 Ayar Altın": "14 Ayar Altın",
    "18 Ayar Altın": "18 Ayar Altın", "Gremse Altın": "Gremse", "Reşat Altın": "Reşat", "Hamit Altın": "Hamit"
}

final_metadata = {
    "borsa_tr_tl": {},
    "borsa_abd_usd": {},
    "kripto_usd": {},
    "doviz_tl": {},
    "altin_tl": {},
    "fon_tl": {}
}

# Avatar Fallback Fonksiyonu
def get_avatar(text, color):
    return f"https://ui-avatars.com/api/?name={text}&background={color}&color=fff&size=128&bold=true"

print("Metadata birleştiriliyor...")

# BIST (ÖZEL İŞLEM - TRADINGVIEW LOGOSU)
for sembol, veri in meta_bist.items():
    # Veri = {"name": "Turk Hava Yollari", "logo": "https://s3...svg"}
    isim = veri["name"]
    logo = veri["logo"]
    
    # Eğer TradingView logo vermediyse eski avatarı kullan
    if not logo:
        logo = get_avatar(sembol, "b30000")
        
    final_metadata["borsa_tr_tl"][sembol] = {"name": isim, "logo": logo}

# ABD
for sembol, isim in meta_abd.items():
    final_metadata["borsa_abd_usd"][sembol] = {"name": isim, "logo": get_avatar(sembol, "0D8ABC")}

# Kripto
for sembol, isim in meta_kripto.items():
    raw_sym = sembol.split("-")[0].lower()
    final_metadata["kripto_usd"][sembol] = {"name": isim, "logo": f"https://assets.coincap.io/assets/icons/{raw_sym}@2x.png"}

# Fon
for sembol, isim in meta_fon.items():
    final_metadata["fon_tl"][sembol] = {"name": isim, "logo": get_avatar(sembol, "27AE60")}

# Döviz
for sembol, isim in meta_doviz.items():
    code = sembol[:3].lower()
    if sembol == "EURUSD": code = "eu"
    if sembol == "GBPUSD": code = "gb"
    final_metadata["doviz_tl"][sembol] = {"name": isim, "logo": f"https://flagcdn.com/w320/{code}.png"}

# Altın
for sembol, isim in meta_altin.items():
    final_metadata["altin_tl"][sembol] = {"name": isim, "logo": "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"}

# KAYIT
print("Veritabanına gönderiliyor...")
doc_ref = db.collection(u'system').document(u'assets_metadata')
doc_ref.set({u'logos': final_metadata}, merge=True)

print("✅ İSİM VE LOGO GÜNCELLEMESİ TAMAMLANDI.")
