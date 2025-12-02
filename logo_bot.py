import requests
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

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
# 1. DÖVİZ LOGOLARI (KUR.DOVIZ.COM - YENİ!)
# ==============================================================================
def get_doviz_metadata():
    print("1. Döviz Logoları (kur.doviz.com) çekiliyor...")
    url = "https://kur.doviz.com/"
    data_doviz = {}
    
    try:
        r = requests.get(url, headers=headers_general, timeout=20)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            satirlar = soup.find_all("tr")
            
            for row in satirlar:
                cols = row.find_all("td")
                # Tablo: [0] İsim+Resim, [1] Kod (USD)
                if len(cols) >= 2:
                    try:
                        kod = cols[1].get_text(strip=True) # USD
                        
                        # İsmi ve Resmi 1. sütundan (cols[0]) al
                        isim_kutusu = cols[0]
                        
                        # İsim (Amerikan Doları)
                        isim = isim_kutusu.get_text(strip=True)
                        
                        # Resim (img tag)
                        img_tag = isim_kutusu.find('img')
                        if img_tag and img_tag.get('src'):
                            logo_url = img_tag['src']
                            
                            # Filtre: Sadece 3 harfli kodları al
                            if len(kod) == 3 and kod.isalpha():
                                data_doviz[kod] = {"name": isim, "logo": logo_url}
                    except: continue
            
            print(f"   -> ✅ Döviz: {len(data_doviz)} adet logo bulundu.")
    except Exception as e:
        print(f"   -> ⚠️ Döviz Hata: {e}")
        
    return data_doviz

# ==============================================================================
# 2. ALTIN LOGOLARI (MANUEL)
# ==============================================================================
def get_altin_metadata():
    print("2. Altın İkonları atanıyor...")
    GOLD = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png"
    SILVER = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png"
    
    altinlar = ["Gram Altın", "Çeyrek Altın", "Yarım Altın", "Tam Altın", "Cumhuriyet A.", "Ata Altın", "Ons Altın", "22 Ayar Bilezik", "14 Ayar Altın", "18 Ayar Altın", "Gremse Altın", "Reşat Altın", "Hamit Altın", "Has Altın"]
    data = {}
    for a in altinlar: data[a] = {"name": a, "logo": GOLD}
    data["Gümüş"] = {"name": "Gümüş", "logo": SILVER}
    return data

# ==============================================================================
# 3. BIST & ABD (TRADINGVIEW)
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
    base_logo = "https://s3-symbol-logo.tradingview.com/"
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=30)
        if r.status_code == 200:
            for h in r.json().get('data', []):
                d = h.get('d', [])
                if len(d) > 2:
                    l_url = f"{base_logo}{d[2]}.svg" if d[2] else None
                    data[d[0]] = {"name": d[1], "logo": l_url}
            print(f"      ✅ {len(data)} adet bulundu.")
    except: pass
    return data

# ==============================================================================
# 4. KRİPTO (CMC API)
# ==============================================================================
def get_crypto_metadata():
    print("4. Kripto Logoları (CMC) çekiliyor...")
    if not CMC_API_KEY: return {}
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '250', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    data = {}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        for coin in r.json()['data']:
            logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin['id']}.png"
            data[f"{coin['symbol']}-USD"] = {"name": coin['name'], "logo": logo}
    except: pass
    print(f"   -> ✅ Kripto: {len(data)} adet.")
    return data

# ==============================================================================
# 5. FONLAR (TEFAS)
# ==============================================================================
def get_fon_metadata():
    print("5. Fon İsimleri çekiliyor...")
    FON_ICON = "https://cdn-icons-png.flaticon.com/512/2910/2910312.png"
    data = {}
    
    # Yedek
    YEDEKLER = {"AFT": "Ak Portföy Yeni Tek.", "TCD": "Tacirler Değ.", "MAC": "Marmara Cap."}
    for k, v in YEDEKLER.items(): data[k] = {"name": v, "logo": FON_ICON}

    # Canlı
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    session = requests.Session()
    try:
        session.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers, timeout=10)
        simdi = datetime.now()
        for i in range(7):
            t_str = (simdi - timedelta(days=i)).strftime("%d.%m.%Y")
            try:
                r = session.post(url, json={"calismatipi": "2", "fontip": "YAT", "bastarih": t_str, "bittarih": t_str}, headers=headers, timeout=30)
                if r.status_code == 200:
                    l = r.json().get('data', [])
                    if len(l) > 50:
                        for f in l:
                            data[f['FONKODU']] = {"name": f['FONADI'], "logo": FON_ICON}
                        print(f"   -> ✅ TEFAS: {len(l)} adet.")
                        return data
            except: continue
    except: pass
    return data

# ==============================================================================
# KAYIT
# ==============================================================================
print("--- LOGO BOTU KAYDEDİLİYOR ---")

# Verileri topla
meta_doviz = get_doviz_metadata() # YENİ!
meta_altin = get_altin_metadata()
meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()

coll_ref = db.collection(u'system_data')

if meta_bist: coll_ref.document(u'bist').set({u'data': meta_bist})
if meta_abd: coll_ref.document(u'abd').set({u'data': meta_abd})
if meta_kripto: coll_ref.document(u'kripto').set({u'data': meta_kripto})
if meta_fon: coll_ref.document(u'fon').set({u'data': meta_fon})

# Döviz ve Altın birleştir
if meta_doviz or meta_altin:
    coll_ref.document(u'doviz_altin').set({
        u'doviz': meta_doviz, 
        u'altin': meta_altin
    })

print("✅ İŞLEM BAŞARIYLA TAMAMLANDI.")
