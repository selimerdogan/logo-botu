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

# --- SABİT İKONLAR (SENİN SEÇTİKLERİN) ---
ICON_GOLD   = "https://cdn-icons-png.freepik.com/512/7401/7401911.png"   # Altınlar
ICON_METAL  = "https://cdn-icons-png.freepik.com/512/18377/18377665.png" # Gümüş, Platin, Paladyum
ICON_FUND   = "https://cdn-icons-png.freepik.com/512/16753/16753112.png" # Fonlar
ICON_OTHER  = "https://cdn-icons-png.freepik.com/512/7480/7480409.png"   # Genel Finans (Yedek)

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
# YARDIMCI: AVATAR OLUŞTURUCU
# ==============================================================================
def get_avatar(text, color):
    """Logo bulunamazsa harfli kutucuk oluşturur"""
    # text: THYAO -> TH
    return f"https://ui-avatars.com/api/?name={text}&background={color}&color=fff&size=128&bold=true"

# ==============================================================================
# 1. BIST & ABD (TRADINGVIEW SCANNER - AVATAR DESTEKLİ)
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
    
    # Pazar rengi (BIST: Kırmızı, ABD: Mavi)
    bg_color = "b30000" if market == "turkey" else "0D8ABC"
    
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
                    
                    # --- MANTIK BURADA DEĞİŞTİ ---
                    if logo_id:
                        # Logo varsa orjinalini kullan
                        logo_url = f"{base_logo_url}{logo_id}.svg"
                    else:
                        # Logo yoksa AVATAR kullan (Harfli kutucuk)
                        logo_url = get_avatar(sembol, bg_color)
                    
                    if "," in isim: isim = isim.split(",")[0]
                    
                    data[sembol] = {"name": isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet veri bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (CMC API)
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC) çekiliyor...")
    
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC Key Yok! Statik liste kullanılacak.")
        LISTE_YEDEK = ["BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "DOGE", "TRX"]
        data = {}
        for c in LISTE_YEDEK:
            logo = f"https://assets.coincap.io/assets/icons/{c.lower()}@2x.png"
            data[f"{c}-USD"] = {"name": c, "logo": logo}
        return data

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
                name = coin['name']
                coin_id = coin['id']
                logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                data[f"{sym}-USD"] = {"name": name, "logo": logo}
            print(f"   -> ✅ CMC: {len(data)} adet kripto metadata alındı.")
    except Exception as e:
        print(f"   -> ⚠️ CMC Hatası: {e}")
        
    return data

# ==============================================================================
# 3. YATIRIM FONLARI (TEFAS - ÖZEL İKONLU)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    data = {}
    
    # Yedekler
    YEDEK_FONLAR = {
        "AFT": "Ak Portföy Yeni Teknolojiler", "TCD": "Tacirler Portföy Değişken", "MAC": "Marmara Capital Hisse",
        "YAY": "Yapı Kredi Yabancı Teknoloji", "TI2": "İş Portföy Teknoloji"
    }
    for kod, isim in YEDEK_FONLAR.items():
        data[kod] = {"name": isim, "logo": ICON_FUND} # Senin seçtiğin Fon İkonu

    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    session = requests.Session()
    
    try:
        session.get("https://www.tefas.gov.tr/FonKarsilastirma.aspx", headers=headers, timeout=10)
        simdi = datetime.now()
        for i in range(7):
            tarih_str = (simdi - timedelta(days=i)).strftime("%d.%m.%Y")
            try:
                r = session.post(url, json={"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}, headers=headers, timeout=30)
                if r.status_code == 200:
                    l = r.json().get('data', [])
                    if len(l) > 50:
                        for f in l:
                            # Tüm fonlara senin seçtiğin ikonu atıyoruz
                            data[f['FONKODU']] = {"name": f['FONADI'], "logo": ICON_FUND}
                        print(f"   -> ✅ TEFAS: {len(l)} adet fon işlendi.")
                        return data
            except: continue
    except: pass
    return data

def get_doviz_altin_metadata():
    print("4. Döviz ve Altın hazırlanıyor...")
    
    # --- DÖVİZ ---
    # Görseldeki eksikler: Rus Rublesi (ru), Çin Yuanı (cn), BAE Dirhemi (ae)
    doviz_map = {
        "USD": {"n": "ABD Doları", "c": "us"},
        "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"},
        "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "CAD": {"n": "Kanada Doları", "c": "ca"},
        "JPY": {"n": "Japon Yeni", "c": "jp"},
        "AUD": {"n": "Avustralya Doları", "c": "au"},
        # --- EKLENENLER ---
        "RUB": {"n": "Rus Rublesi", "c": "ru"},   # Görselde var, ekledim
        "CNY": {"n": "Çin Yuanı", "c": "cn"},     # Görselde var, ekledim
        "AED": {"n": "BAE Dirhemi", "c": "ae"},   # Görselde var, ekledim
        # İsteğe bağlı eklenebilecekler (Görselde yok ama popüler):
        # "SAR": {"n": "Suudi Arabistan Riyali", "c": "sa"},
        # "DKK": {"n": "Danimarka Kronu", "c": "dk"},
        # "SEK": {"n": "İsveç Kronu", "c": "se"}
    }

    # API'den veri çekerken kullanılacak sembol listesi (Yahoo Finance formatı genelde)
    liste_doviz = [
        "USDTRY", "EURTRY", "GBPTRY", "CHFTRY", 
        "CADTRY", "JPYTRY", "AUDTRY", 
        "RUBTRY", "CNYTRY", "AEDTRY" # Listeye de eklemeyi unutmuyoruz
    ]

    data_doviz = {}
    for kur in liste_doviz:
        # Kod temizleme: "USDTRY" -> "USD"
        kod = kur.replace("TRY", "").replace("=X", "")
        
        if kod in doviz_map:
            info = doviz_map[kod]
            # Bayrak servisi flagcdn kullanarak ülke koduyla (c) ikon oluşturuyoruz
            data_doviz[kur] = {
                "name": info["n"], 
                "logo": f"https://flagcdn.com/w320/{info['c']}.png"
            }
            
    # --- ALTIN & METALLER ---
    data_altin = {}
    
    # İsimleri siteden çekiyoruz (Doviz.com)
    try:
        r = requests.get("https://altin.doviz.com/", headers=headers_general, timeout=20)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.content, "html.parser")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) > 2:
                isim = tds[0].get_text(strip=True)
                
                # İKON SEÇİMİ
                if "Gümüş" in isim or "Platin" in isim or "Paladyum" in isim:
                    secilen_ikon = ICON_METAL # Gri Metal İkonu
                else:
                    secilen_ikon = ICON_GOLD # Sarı Altın İkonu
                
                if "Ons" not in isim:
                    data_altin[isim] = {"name": isim, "logo": secilen_ikon}
                    
    except Exception as e:
        print(f"   -> ⚠️ Altın İsim Hatası: {e}")
    
    # Manuel eklemeler (Garanti olsun diye)
    if "Platin" not in data_altin: data_altin["Platin"] = {"name": "Platin", "logo": ICON_METAL}
    if "Paladyum" not in data_altin: data_altin["Paladyum"] = {"name": "Paladyum", "logo": ICON_METAL}
    if "Gümüş" not in data_altin: data_altin["Gümüş"] = {"name": "Gümüş", "logo": ICON_METAL}
    
    return data_doviz, data_altin
# ==============================================================================
# KAYIT
# ==============================================================================
print("--- LOGO/METADATA KAYDEDİLİYOR ---")

meta_bist = get_tradingview_metadata("turkey")
meta_abd = get_tradingview_metadata("america")
meta_kripto = get_crypto_metadata()
meta_fon = get_fon_metadata()
meta_doviz, meta_altin = get_doviz_altin_metadata()

coll_ref = db.collection(u'system_data')

if meta_bist: coll_ref.document(u'bist').set({u'data': meta_bist})
if meta_abd: coll_ref.document(u'abd').set({u'data': meta_abd})
if meta_kripto: coll_ref.document(u'kripto').set({u'data': meta_kripto})
if meta_fon: coll_ref.document(u'fon').set({u'data': meta_fon})

if meta_doviz or meta_altin:
    coll_ref.document(u'doviz_altin').set({
        u'doviz': meta_doviz, 
        u'altin': meta_altin
    })

print("✅ LOGO GÜNCELLEMESİ TAMAMLANDI.")
