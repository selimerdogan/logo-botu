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

# --- SABİT İKONLAR ---
ICON_GOLD   = "https://cdn-icons-png.freepik.com/512/7401/7401911.png"
ICON_METAL  = "https://cdn-icons-png.freepik.com/512/18377/18377665.png"
ICON_FUND   = "https://cdn-icons-png.freepik.com/512/16753/16753112.png"

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

def get_avatar(text, color):
    return f"https://ui-avatars.com/api/?name={text}&background={color}&color=fff&size=128&bold=true"

# ==============================================================================
# 1. BIST & ABD (Piyasa Botu ile aynı anahtar: "THYAO", "AAPL")
# ==============================================================================
def get_tradingview_metadata(market):
    print(f"   -> {market.upper()} Logoları aranıyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"],
        "range": [0, 4000] 
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    bg_color = "b30000" if market == "turkey" else "0D8ABC"
    
    try:
        r = requests.post(url, json=payload, headers=headers_general, timeout=45)
        if r.status_code == 200:
            items = r.json().get('data', [])
            for h in items:
                d = h.get('d', [])
                if len(d) > 2:
                    sembol = d[0] # Örn: THYAO
                    isim = d[1]   # Örn: Turk Hava Yollari
                    logo_id = d[2]
                    
                    if logo_id:
                        logo_url = f"{base_logo_url}{logo_id}.svg"
                    else:
                        logo_url = get_avatar(sembol, bg_color)
                    
                    if "," in isim: isim = isim.split(",")[0]
                    
                    # KRİTİK NOKTA: Anahtar 'sembol' olmalı.
                    data[sembol] = {"name": isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet veri bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (Piyasa Botu ile aynı anahtar: "BTC-USD")
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC) çekiliyor...")
    
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC Key Yok! Statik liste.")
        return {}

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '300', 'convert': 'USD'} # Piyasa botunda 250 demiştik, burada 300 yapalım garanti olsun
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    data = {}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            coins = r.json()['data']
            for coin in coins:
                sym = coin['symbol']
                name = coin['name']
                coin_id = coin['id']
                logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                
                # KRİTİK NOKTA: Piyasa botun "BTC-USD" formatında kaydediyor.
                # Burası da aynısı olmalı.
                key = f"{sym}-USD"
                data[key] = {"name": name, "logo": logo}
            print(f"   -> ✅ CMC: {len(data)} adet kripto metadata alındı.")
    except Exception as e:
        print(f"   -> ⚠️ CMC Hatası: {e}")
        
    return data

# ==============================================================================
# 3. FONLAR (Piyasa Botu ile aynı anahtar: "AFT", "TCD")
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    data = {}
    
    # TEFAS'tan toplu çekip isimleri alıyoruz
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    
    try:
        # Son tarihi bulup istek atıyoruz
        simdi = datetime.now()
        tarih_str = simdi.strftime("%d.%m.%Y")
        
        # Sadece son 1 günün verisi fon isimlerini almak için yeterli
        payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
        
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            l = r.json().get('data', [])
            if len(l) > 0:
                for f in l:
                    kod = f['FONKODU']
                    isim = f['FONADI']
                    # Piyasa botunda anahtar direkt FON KODU (Örn: AFT)
                    data[kod] = {"name": isim, "logo": ICON_FUND}
                print(f"   -> ✅ TEFAS: {len(data)} adet fon işlendi.")
    except Exception as e: 
        print(f"Hata: {e}")
    
    return data

# ==============================================================================
# 4. DÖVİZ & ALTIN (Piyasa Botu Eşleşmesi İçin KRİTİK ALAN)
# ==============================================================================
def get_doviz_altin_metadata():
    print("4. Döviz ve Altın hazırlanıyor...")
    
    # --- DÖVİZ EŞLEŞTİRME ---
    # Piyasa botun "USD", "EUR" anahtarlarını kullanıyor.
    # Logo botun eskiden "USDTRY" kullanıyordu. Bunu düzeltiyoruz.
    
    doviz_config = {
        "USD": {"n": "ABD Doları", "c": "us"},
        "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"},
        "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "CAD": {"n": "Kanada Doları", "c": "ca"},
        "JPY": {"n": "Japon Yeni", "c": "jp"},
        "RUB": {"n": "Rus Rublesi", "c": "ru"},
        "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "BAE": {"n": "BAE Dirhemi", "c": "ae"}, # Piyasa botun "BAE" kodunu kullanıyor (dikkat)
        "AUD": {"n": "Avustralya Doları", "c": "au"}
    }

    data_doviz = {}
    for kod, info in doviz_config.items():
        # ANAHTAR = "USD" (Piyasa botuyla aynı)
        data_doviz[kod] = {
            "name": info["n"], 
            "logo": f"https://flagcdn.com/w320/{info['c']}.png"
        }
            
    # --- ALTIN EŞLEŞTİRME ---
    # Piyasa botun isimleri direkt siteden (Doviz.com) alıyor: "Gram Altın", "Çeyrek Altın" vs.
    # Biz de isimleri aynı siteden çekelim ki harfiyen tutsun.
    data_altin = {}
    
    try:
        r = requests.get("https://altin.doviz.com/", headers=headers_general, timeout=20)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.content, "html.parser")
        
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) > 2:
                isim = tds[0].get_text(strip=True) # Örn: "Gram Altın"
                
                if "Ons" not in isim:
                    # İKON MANTIĞI
                    if any(x in isim for x in ["Gümüş", "Platin", "Paladyum"]):
                        ikon = ICON_METAL
                    else:
                        ikon = ICON_GOLD
                    
                    # ANAHTAR = "Gram Altın" (Piyasa botuyla aynı)
                    data_altin[isim] = {"name": isim, "logo": ikon}
                    
    except Exception as e:
        print(f"   -> ⚠️ Altın İsim Hatası: {e}")
    
    return data_doviz, data_altin

# ==============================================================================
# KAYIT
# ==============================================================================
print("--- LOGO/METADATA KAYDEDİLİYOR (EŞLEŞTİRİLMİŞ VERSİYON) ---")

meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()
meta_doviz, meta_altin = get_doviz_altin_metadata()

coll_ref = db.collection(u'system_data')

# 1. BIST
if meta_bist: coll_ref.document(u'bist').set({u'data': meta_bist})

# 2. ABD
if meta_abd: coll_ref.document(u'abd').set({u'data': meta_abd})

# 3. KRİPTO
if meta_kripto: coll_ref.document(u'kripto').set({u'data': meta_kripto})

# 4. FONLAR
if meta_fon: coll_ref.document(u'fon').set({u'data': meta_fon})

# 5. DÖVİZ & ALTIN (Tek dokümanda veya ayrı ayrı tutabilirsin, burada birleştirdim)
# Piyasa botunda "doviz_tl" ve "altin_tl" diye geçiyor.
# Uygulama tarafında kolaylık olsun diye burada ayırabiliriz de.
if meta_doviz or meta_altin:
    coll_ref.document(u'doviz_altin').set({
        u'doviz': meta_doviz, 
        u'altin': meta_altin
    })

print("✅ LOGO GÜNCELLEMESİ TAMAMLANDI.")
