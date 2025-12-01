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
CMC_API_KEY = os.environ.get('CMC_API_KEY') # Kripto isimleri için şart

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
# 1. BIST & ABD (TRADINGVIEW - UZUN İSİMLER)
# ==============================================================================
def get_tradingview_metadata(market):
    """
    TradingView'den Uzun İsim (Description) ve Logo çeker.
    """
    print(f"   -> {market.upper()} İsimleri ve Logoları aranıyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"}, # Türkçe karakterler için
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"], # description = UZUN İSİM
        "range": [0, 3000] 
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=30)
        if r.status_code == 200:
            items = r.json().get('data', [])
            for h in items:
                d = h.get('d', [])
                if len(d) > 2:
                    sembol = d[0]          # AAPL
                    uzun_isim = d[1]       # Apple Inc.
                    logo_id = d[2]
                    
                    # Logo Linki
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    
                    # İsim Düzeltme (Gereksiz virgülleri at)
                    if "," in uzun_isim: uzun_isim = uzun_isim.split(",")[0]
                    
                    data[sembol] = {"name": uzun_isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet veri (Uzun İsimli) bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (COINMARKETCAP TOP 250 - UZUN İSİMLER)
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto (Top 250) İsimleri ve Logoları çekiliyor...")
    data = {}
    
    # API Key varsa CMC'den çek (En Doğrusu)
    if CMC_API_KEY:
        url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
        params = {'start': '1', 'limit': '250', 'convert': 'USD'} # İLK 250
        headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=20)
            if r.status_code == 200:
                coins = r.json()['data']
                for coin in coins:
                    sym = coin['symbol'] # BTC
                    name = coin['name']  # Bitcoin
                    coin_id = coin['id']
                    
                    # CMC Resmi Logo Sunucusu (Yüksek Kalite)
                    logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                    
                    data[f"{sym}-USD"] = {"name": name, "logo": logo}
                
                print(f"   -> ✅ CMC: {len(data)} adet kripto tam ismiyle alındı.")
                return data
        except Exception as e:
            print(f"   -> ⚠️ CMC Hatası: {e}")
    
    # API Yoksa veya Hata Verdiyse Yedek Statik Liste (Boş kalmasın)
    print("   -> ⚠️ Yedek Kripto Listesi Kullanılıyor...")
    YEDEK_LISTE = [
        ("BTC", "Bitcoin"), ("ETH", "Ethereum"), ("BNB", "BNB"), ("SOL", "Solana"), 
        ("XRP", "XRP"), ("ADA", "Cardano"), ("AVAX", "Avalanche"), ("DOGE", "Dogecoin"),
        ("TRX", "Tron"), ("DOT", "Polkadot"), ("LINK", "Chainlink"), ("SHIB", "Shiba Inu")
    ]
    for sym, name in YEDEK_LISTE:
        logo = f"https://assets.coincap.io/assets/icons/{sym.lower()}@2x.png"
        data[f"{sym}-USD"] = {"name": name, "logo": logo}
        
    return data

# ==============================================================================
# 3. YATIRIM FONLARI (TEFAS - UZUN İSİMLER)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png"
    data = {}
    
    # --- YEDEK LİSTE (Önemli Fonların Tam Adları) ---
    YEDEK_FONLAR = {
        "AFT": "Ak Portföy Yeni Teknolojiler Yabancı Hisse Senedi Fonu",
        "TCD": "Tacirler Portföy Değişken Fon",
        "MAC": "Marmara Capital Hisse Senedi Fonu (Hisse Senedi Yoğun Fon)",
        "YAY": "Yapı Kredi Portföy Yabancı Teknoloji Sektörü Hisse Senedi Fonu",
        "IPJ": "İş Portföy Elektrikli Araçlar Karma Fon",
        "NNF": "Hedef Portföy Birinci Hisse Senedi Fonu",
        "TI2": "İş Portföy BIST Teknoloji Ağırlıklı Sınırlamalı Endeks Hisse Senedi Fonu",
        "AES": "Ak Portföy Petrol Yabancı BYF Fon Sepeti Fonu",
        "GMR": "Inveo Portföy Gümüş Fon Sepeti Fonu"
    }
    
    # Önce yedekleri doldur
    for kod, isim in YEDEK_FONLAR.items():
        data[kod] = {"name": isim, "logo": FON_ICON}

    # Sonra TEFAS'tan güncel çek
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    session = requests.Session()
    
    try:
        session.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers, timeout=10)
        simdi = datetime.now()
        for i in range(7):
            tarih_str = (simdi - timedelta(days=i)).strftime("%d.%m.%Y")
            try:
                payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
                r = session.post(url, json=payload, headers=headers, timeout=30)
                if r.status_code == 200:
                    fon_listesi = r.json().get('data', [])
                    if len(fon_listesi) > 50:
                        for f in fon_listesi:
                            # TEFAS 'FONADI' zaten uzun isimdir
                            data[f['FONKODU']] = {"name": f['FONADI'], "logo": FON_ICON}
                        print(f"   -> ✅ TEFAS'tan {len(fon_listesi)} adet uzun isim çekildi.")
                        return data
            except: continue
    except: pass
    
    print(f"   -> ⚠️ TEFAS yanıt vermedi, {len(data)} adet yedek isim kullanılıyor.")
    return data

# ==============================================================================
# 4. DÖVİZ & ALTIN (MANUEL UZUN İSİMLER)
# ==============================================================================
def get_doviz_altin_metadata():
    print("4. Döviz ve Altın hazırlanıyor...")
    data_doviz = {}
    doviz_map = {
        "USD": {"n": "Amerikan Doları", "c": "us"}, 
        "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"}, 
        "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "CAD": {"n": "Kanada Doları", "c": "ca"}, 
        "JPY": {"n": "Japon Yeni", "c": "jp"},
        "AUD": {"n": "Avustralya Doları", "c": "au"}, 
        "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "EURUSD": {"n": "Euro / Amerikan Doları", "c": "eu"}, 
        "GBPUSD": {"n": "Sterlin / Amerikan Doları", "c": "gb"},
        "DX-Y": {"n": "ABD Dolar Endeksi", "c": "us"}
    }
    liste_doviz = ["USDTRY", "EURTRY", "GBPTRY", "CHFTRY", "CADTRY", "JPYTRY", "AUDTRY", "EURUSD", "GBPUSD", "DX-Y"]
    for kur in liste_doviz:
        kod = kur.replace("TRY", "").replace("=X", "")
        if kod in doviz_map:
            info = doviz_map[kod]
            data_doviz[kur] = {"name": info["n"], "logo": f"https://flagcdn.com/w320/{info['c']}.png"}
            
    data_altin = {}
    GOLD_ICON = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"
    SILVER_ICON = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png"
    # Altın uzun isimleri
    altinlar = {
        "Gram Altın": "24 Ayar Gram Altın", 
        "Çeyrek Altın": "Çeyrek Altın (Yeni)", 
        "Yarım Altın": "Yarım Altın (Yeni)", 
        "Tam Altın": "Tam Altın (Yeni)", 
        "Cumhuriyet A.": "Cumhuriyet Altını", 
        "Ata Altın": "Ata Lira", 
        "Ons Altın": "Uluslararası Ons Altın", 
        "22 Ayar Bilezik": "22 Ayar Bilezik (Gram)", 
        "14 Ayar Altın": "14 Ayar Altın (Gram)", 
        "18 Ayar Altın": "18 Ayar Altın (Gram)", 
        "Gremse Altın": "Gremse Altın (2.5'luk)", 
        "Reşat Altın": "Reşat Altın", 
        "Hamit Altın": "Hamit Altın"
    }
    
    for k, v in altinlar.items():
        data_altin[k] = {"name": v, "logo": GOLD_ICON}
    data_altin["Gümüş"] = {"name": "Gümüş (Gram)", "logo": SILVER_ICON}
    
    return data_doviz, data_altin

# ==============================================================================
# ANA İŞLEM
# ==============================================================================

print("--- LOGO BOTU ÇALIŞIYOR (UZUN İSİMLER) ---")

meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()
meta_doviz, meta_altin = get_doviz_altin_metadata()

# Birleştir
final_metadata = {
    "borsa_tr_tl": meta_bist,
    "borsa_abd_usd": meta_abd,
    "kripto_usd": meta_kripto,
    "fon_tl": meta_fon,
    "doviz_tl": meta_doviz,
    "altin_tl": meta_altin
}

print("Veritabanına gönderiliyor...")
doc_ref = db.collection(u'system').document(u'assets_metadata')
doc_ref.set({u'logos': final_metadata}, merge=True)

print("✅ İSİM VE LOGO GÜNCELLEMESİ TAMAMLANDI.")
