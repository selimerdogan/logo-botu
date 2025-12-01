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
# 1. BIST & ABD (TRADINGVIEW SCANNER)
# ==============================================================================
def get_tradingview_metadata(market):
    print(f"   -> {market.upper()} Logoları aranıyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"],
        "range": [0, 3000] 
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
                    isim = d[1]
                    logo_id = d[2]
                    
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    data[sembol] = {"name": isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet logo bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (COINMARKETCAP API - TOP 250)
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC API - Top 250) çekiliyor...")
    
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC API Key yok! Kripto logoları çekilemiyor.")
        return {}

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    # Fiyat botu ile aynı parametreler: Top 250
    params = {'start': '1', 'limit': '250', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    
    data = {}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            coins = r.json()['data']
            for coin in coins:
                sym = coin['symbol']  # BTC
                name = coin['name']   # Bitcoin
                coin_id = coin['id']  # 1
                
                # CMC'nin resmi yüksek kaliteli logo sunucusu
                logo_url = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                
                # Anahtar formatı fiyat botuyla aynı olmalı: "BTC-USD"
                data[f"{sym}-USD"] = {"name": name, "logo": logo_url}
            
            print(f"   -> ✅ CMC: {len(data)} adet logo ve isim alındı.")
        else:
            print(f"   -> ⚠️ CMC Hatası: {r.status_code}")
    except Exception as e:
        print(f"   -> ⚠️ Bağlantı Hatası: {e}")
        
    return data

# ==============================================================================
# 3. YATIRIM FONLARI (TEFAS + YEDEK LİSTE)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png"
    data = {}
    
    # --- YEDEK LİSTE ---
    YEDEK_FONLAR = {
        "AFT": "Ak Portföy Yeni Teknolojiler", "TCD": "Tacirler Portföy Değişken", "MAC": "Marmara Capital Hisse",
        "YAY": "Yapı Kredi Yabancı Teknoloji", "IPJ": "İş Portföy Elektrikli Araçlar", "NNF": "Hedef Portföy Birinci",
        "TI2": "İş Portföy BIST Teknoloji", "AES": "Ak Portföy Petrol", "GMR": "Inveo Portföy Gümüş",
        "ADP": "Ak Portföy BIST 30", "IHK": "İş Portföy BIST 100 Dışı", "IDH": "İş Portföy BIST Temettü"
    }
    for kod, isim in YEDEK_FONLAR.items():
        data[kod] = {"name": isim, "logo": FON_ICON}

    # --- CANLI ÇEKİM ---
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    session = requests.Session()
    
    try:
        session.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers, timeout=10)
        simdi = datetime.now()
        # 7 gün geriye git
        for i in range(7):
            tarih_str = (simdi - timedelta(days=i)).strftime("%d.%m.%Y")
            try:
                payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
                r = session.post(url, json=payload, headers=headers, timeout=30)
                if r.status_code == 200:
                    fon_listesi = r.json().get('data', [])
                    if len(fon_listesi) > 50:
                        for f in fon_listesi:
                            data[f['FONKODU']] = {"name": f['FONADI'], "logo": FON_ICON}
                        print(f"   -> ✅ TEFAS: {len(fon_listesi)} adet güncel isim alındı.")
                        return data
            except: continue
    except: pass
    
    print(f"   -> ⚠️ TEFAS yanıt vermedi, {len(data)} adet yedek fon kullanılıyor.")
    return data

# ==============================================================================
# 4. DÖVİZ & ALTIN
# ==============================================================================
def get_doviz_altin_metadata():
    print("4. Döviz ve Altın hazırlanıyor...")
    
    # Döviz
    doviz_map = {
        "USD": {"n": "ABD Doları", "c": "us"}, "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"}, "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "CAD": {"n": "Kanada Doları", "c": "ca"}, "JPY": {"n": "Japon Yeni", "c": "jp"},
        "AUD": {"n": "Avustralya Doları", "c": "au"}, "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "EURUSD": {"n": "Euro/Dolar", "c": "eu"}, "GBPUSD": {"n": "Sterlin/Dolar", "c": "gb"},
        "DX-Y": {"n": "Dolar Endeksi", "c": "us"}
    }
    liste_doviz = ["USDTRY", "EURTRY", "GBPTRY", "CHFTRY", "CADTRY", "JPYTRY", "AUDTRY", "EURUSD", "GBPUSD", "DX-Y"]
    data_doviz = {}
    for kur in liste_doviz:
        kod = kur.replace("TRY", "").replace("=X", "")
        if kod in doviz_map:
            info = doviz_map[kod]
            data_doviz[kur] = {"name": info["n"], "logo": f"https://flagcdn.com/w320/{info['c']}.png"}

    # Altın
    GOLD = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"
    SILVER = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png"
    altinlar = ["Gram Altın", "Çeyrek Altın", "Yarım Altın", "Tam Altın", "Cumhuriyet A.", "Ata Altın", "Ons Altın", "22 Ayar Bilezik", "14 Ayar Altın", "18 Ayar Altın", "Gremse Altın", "Reşat Altın", "Hamit Altın"]
    data_altin = {}
    for a in altinlar: data_altin[a] = {"name": a, "logo": GOLD}
    data_altin["Gümüş"] = {"name": "Gümüş", "logo": SILVER}
    
    return data_doviz, data_altin

# ==============================================================================
# KAYIT (PARÇALI KOLEKSİYON - SYSTEM_DATA)
# ==============================================================================
print("--- LOGO/METADATA KAYDEDİLİYOR ---")

# Verileri hafızaya al
meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()
meta_doviz, meta_altin = get_doviz_altin_metadata()

# Koleksiyon Adı: system_data
coll_ref = db.collection(u'system_data')

# Parçalı Kayıt (Limitlere Takılmamak İçin)
if meta_bist: 
    print("BIST kaydediliyor...")
    coll_ref.document(u'bist').set({u'data': meta_bist})

if meta_abd: 
    print("ABD kaydediliyor...")
    coll_ref.document(u'abd').set({u'data': meta_abd})

if meta_kripto: 
    print(f"Kripto ({len(meta_kripto)} adet) kaydediliyor...")
    coll_ref.document(u'kripto').set({u'data': meta_kripto})

if meta_fon: 
    print("Fonlar kaydediliyor...")
    coll_ref.document(u'fon').set({u'data': meta_fon})

if meta_doviz or meta_altin:
    print("Döviz/Altın kaydediliyor...")
    coll_ref.document(u'doviz_altin').set({
        u'doviz': meta_doviz, 
        u'altin': meta_altin
    })

print("✅ TÜM VERİLER BA
