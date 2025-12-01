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
        "range": [0, 2000]
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=30)
        if r.status_code == 200:
            for h in r.json().get('data', []):
                d = h.get('d', [])
                if len(d) > 2:
                    sembol = d[0]
                    isim = d[1]
                    logo_id = d[2]
                    
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    data[sembol] = {"name": isim, "logo": logo_url}
    except Exception as e:
        print(f"   -> Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (API GEREKTİRMEYEN STATİK LİSTE)
# ==============================================================================
# CMC Anahtarı ile uğraşmayalım, CoinCap'in açık kaynak ikonlarını kullanalım.
def get_crypto_metadata():
    print("2. Kripto Logoları (Statik) hazırlanıyor...")
    
    # En popüler coinlerin listesi
    LISTE_KRIPTO = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "TRX", "DOT", "LINK", "LTC", "SHIB", "ATOM", "XLM", "ALGO", "SAND", "MANA", "EOS", "NEAR", "FIL", "APE", "QNT", "PEPE", "ARB", "OP", "SUI", "APT", "RNDR", "GRT", "INJ", "FET", "GALA", "LDO", "FTM", "UNI", "AAVE", "SNX", "MKR", "CRV", "CHZ", "STX", "IMX", "MINA", "AXS", "EGLD", "THETA", "XTZ", "NEO", "EOS", "IOTA", "KAS", "SEI", "TIA", "WLD", "BONK", "FLOKI", "WIF"
    ]
    
    data = {}
    for coin in LISTE_KRIPTO:
        # CoinCap standart ikon URL yapısı
        logo = f"https://assets.coincap.io/assets/icons/{coin.lower()}@2x.png"
        data[f"{coin}-USD"] = {"name": coin, "logo": logo}
        
    print(f"   -> ✅ Kripto: {len(data)} adet logo hazır.")
    return data

# ==============================================================================
# 3. YATIRIM FONLARI (TEFAS - GERİYE DÖNÜK TARAMA)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    
    headers = {
        "User-Agent": "Mozilla/5.0", 
        "X-Requested-With": "XMLHttpRequest", 
        "Referer": "https://www.tefas.gov.tr", 
        "Content-Type": "application/json"
    }
    
    session = requests.Session()
    try: session.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers)
    except: pass
    
    simdi = datetime.now()
    data = {}
    
    # 5 gün geriye git (Veri bulana kadar)
    for i in range(5):
        tarih_obj = simdi - timedelta(days=i)
        tarih_str = tarih_obj.strftime("%d.%m.%Y")
        
        try:
            payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
            r = session.post(url, json=payload, headers=headers, timeout=30)
            
            if r.status_code == 200:
                fon_listesi = r.json().get('data', [])
                if len(fon_listesi) > 50:
                    # Standart Fon İkonu
                    FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png"
                    
                    for f in fon_listesi:
                        data[f['FONKODU']] = {"name": f['FONADI'], "logo": FON_ICON}
                        
                    print(f"   -> ✅ Fon: {len(data)} adet isim bulundu ({tarih_str}).")
                    return data
        except: continue
        
    print("   -> ❌ Fon: Veri bulunamadı.")
    return {}

# ==============================================================================
# 4. DÖVİZ & ALTIN (MANUEL TANIMLAR)
# ==============================================================================
def get_doviz_altin_metadata():
    print("4. Döviz ve Altın hazırlanıyor...")
    data_doviz = {}
    
    # Döviz İsim ve Bayrakları
    doviz_map = {
        "USD": {"n": "ABD Doları", "c": "us"}, "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"}, "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "CAD": {"n": "Kanada Doları", "c": "ca"}, "JPY": {"n": "Japon Yeni", "c": "jp"},
        "AUD": {"n": "Avustralya Doları", "c": "au"}, "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "EURUSD": {"n": "Euro / Dolar", "c": "eu"}, "GBPUSD": {"n": "Sterlin / Dolar", "c": "gb"},
        "DX-Y": {"n": "Dolar Endeksi", "c": "us"}
    }
    
    liste_doviz = ["USDTRY", "EURTRY", "GBPTRY", "CHFTRY", "CADTRY", "JPYTRY", "AUDTRY", "EURUSD", "GBPUSD", "DX-Y"]
    
    for kur in liste_doviz:
        kod = kur.replace("TRY", "").replace("=X", "")
        if kod in doviz_map:
            info = doviz_map[kod]
            data_doviz[kur] = {
                "name": info["n"],
                "logo": f"https://flagcdn.com/w320/{info['c']}.png"
            }
            
    # Altın İsimleri
    data_altin = {}
    GOLD_ICON = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"
    SILVER_ICON = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png"
    
    altinlar = ["Gram Altın", "Çeyrek Altın", "Yarım Altın", "Tam Altın", "Cumhuriyet A.", "Ata Altın", "Ons Altın", "22 Ayar Bilezik", "14 Ayar Altın", "18 Ayar Altın", "Gremse Altın", "Reşat Altın", "Hamit Altın"]
    
    for a in altinlar:
        data_altin[a] = {"name": a, "logo": GOLD_ICON}
    data_altin["Gümüş"] = {"name": "Gümüş", "logo": SILVER_ICON}
    
    return data_doviz, data_altin

# ==============================================================================
# ANA İŞLEM
# ==============================================================================

print("--- LOGO BOTU ÇALIŞIYOR ---")

meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()
meta_doviz, meta_altin = get_doviz_altin_metadata()

# Avatar Fallback
def get_avatar(text, color):
    return f"https://ui-avatars.com/api/?name={text}&background={color}&color=fff&size=128&bold=true"

# Eksik logoları doldur
for sembol, veri in meta_bist.items():
    if not veri.get('logo'): veri['logo'] = get_avatar(sembol, "b30000")

for sembol, veri in meta_abd.items():
    if not veri.get('logo'): veri['logo'] = get_avatar(sembol, "0D8ABC")

# Birleştir
final_metadata = {
    "borsa_tr_tl": meta_bist,
    "borsa_abd_usd": meta_abd,
    "kripto_usd": meta_kripto,
    "fon_tl": meta_fon,
    "doviz_tl": meta_doviz,
    "altin_tl": meta_altin
}

print("Veritabanına kaydediliyor...")
# HATA DÜZELTİLDİ: 'doc' değil 'doc_ref'
doc_ref = db.collection(u'system').document(u'assets_metadata')
doc_ref.set({u'logos': final_metadata}, merge=True)

print("✅ İŞLEM BAŞARIYLA TAMAMLANDI.")
