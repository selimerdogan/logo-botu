import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import sys
import json
import io
import uuid 
from PIL import Image 
from datetime import datetime

# --- GENEL AYARLAR ---
headers_general = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- KİMLİK KONTROLLERİ VE BAŞLATMA ---
firebase_key_str = os.environ.get('FIREBASE_KEY')
CMC_API_KEY = os.environ.get('CMC_API_KEY')
BUCKET_NAME = "vario-264d9.firebasestorage.app"

if not firebase_key_str:
    if os.path.exists("serviceAccountKey.json"):
        cred = credentials.Certificate("serviceAccountKey.json")
    else:
        print("HATA: Anahtar (FIREBASE_KEY) bulunamadı!")
        sys.exit(1)
else:
    cred_dict = json.loads(firebase_key_str)
    cred = credentials.Certificate(cred_dict)

try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_NAME})
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    print(f"HATA: Firebase hatası: {e}")
    sys.exit(1)

# ==============================================================================
# YARDIMCI: VERİYİ PARÇALA VE KAYDET (1MB LİMİTİ İÇİN)
# ==============================================================================
def save_data_in_chunks(collection_name, base_doc_name, big_data, chunk_size=2000):
    """
    Firestore 1MB limitini aşmamak için veriyi abd_1, abd_2 gibi böler.
    """
    coll_ref = db.collection(collection_name)
    items = list(big_data.items())
    total_items = len(items)
    
    # Parça sayısını hesapla
    total_chunks = (total_items // chunk_size) + 1
    
    print(f"   💾 '{base_doc_name}' verisi {total_chunks} parçaya bölünüyor ({total_items} kayıt)...")

    for i in range(total_chunks):
        start = i * chunk_size
        end = start + chunk_size
        chunk_items = items[start:end]
        
        if not chunk_items: continue
        
        chunk_dict = dict(chunk_items)
        doc_name = f"{base_doc_name}_{i+1}" # Örn: abd_1, abd_2
        
        try:
            coll_ref.document(doc_name).set({u'data': chunk_dict})
            print(f"      ✅ {doc_name} kaydedildi ({len(chunk_dict)} kayıt).")
        except Exception as e:
            print(f"      ❌ {doc_name} kaydederken hata: {e}")

# ==============================================================================
# YARDIMCI FONKSİYON: RESMİ YÜKLE
# ==============================================================================
def upload_logo(original_url, file_name, folder_name):
    if "firebasestorage.googleapis.com" in original_url or "flagcdn.com" in original_url:
        return original_url
    if "ui-avatars.com" in original_url or not original_url:
        return original_url

    try:
        resp = requests.get(original_url, headers=headers_general, timeout=15)
        if resp.status_code != 200: return original_url 

        content_type = resp.headers.get('Content-Type', '')
        file_data = resp.content
        
        if "svg" in content_type or original_url.endswith(".svg") or b"<svg" in file_data[:100]:
            extension = "svg"
            final_content_type = "image/svg+xml"
            blob_data = file_data
        else:
            img_bytes = io.BytesIO(file_data)
            img = Image.open(img_bytes)
            if img.mode != 'RGBA': img = img.convert('RGBA')
            img = img.resize((128, 128), Image.Resampling.LANCZOS)
            output_io = io.BytesIO()
            img.save(output_io, format='PNG', optimize=True)
            blob_data = output_io.getvalue()
            extension = "png"
            final_content_type = "image/png"

        blob_path = f"logos/{folder_name}/{file_name}.{extension}"
        blob = bucket.blob(blob_path)
        new_token = str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": new_token}
        blob.upload_from_string(blob_data, content_type=final_content_type)
        
        encoded_path = blob_path.replace("/", "%2F") 
        download_url = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media&token={new_token}"
        return download_url

    except Exception as e:
        return original_url 

# ==============================================================================
# 1. BIST & ABD 
# ==============================================================================
def get_tradingview_metadata(market):
    print(f"   -> {market.upper()} Logoları aranıyor ve yükleniyor...")
    url = f"https://scanner.tradingview.com/{market}/scan"
    
    headers_tv = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.tradingview.com",
        "Content-Type": "application/json"
    }
    
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "tr"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"],
        "range": [0, 6000] 
    }
    
    data = {}
    base_logo_url = "https://s3-symbol-logo.tradingview.com/"
    bg_color = "b30000" if market == "turkey" else "0D8ABC"
    
    try:
        r = requests.post(url, json=payload, headers=headers_tv, timeout=60)
        if r.status_code != 200: return {}

        items = r.json().get('data', [])
        print(f"      ℹ️  TradingView'dan {len(items)} veri çekildi.")
        
        count = 0
        for h in items:
            d = h.get('d', [])
            if len(d) > 2:
                sembol = d[0] 
                isim = d[1]    
                logo_id = d[2]
                
                if logo_id:
                    raw_url = f"{base_logo_url}{logo_id}.svg"
                    folder_name = f"stocks_{market}" 
                    final_logo = upload_logo(raw_url, sembol, folder_name)
                else:
                    final_logo = f"https://ui-avatars.com/api/?name={sembol}&background={bg_color}&color=fff&size=128&bold=true"
                
                if "," in isim: isim = isim.split(",")[0]
                data[sembol] = {"name": isim, "logo": final_logo}
                count += 1
                if count % 500 == 0: print(f"      Processing... {count}/{len(items)}")

        print(f"      ✅ {market.upper()}: {len(data)} adet logo işlendi.")
    except Exception as e:
        print(f"      ⛔ HATA (TradingView): {e}")
        
    return data

# ==============================================================================
# 2. KRİPTO
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC) çekiliyor...")
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC Key Yok!")
        return {}

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '300', 'convert': 'USD'}
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
                raw_logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                key = f"{sym}-USD"
                final_logo = upload_logo(raw_logo, key, "crypto")
                data[key] = {"name": name, "logo": final_logo}
            print(f"   -> ✅ CMC: {len(data)} adet kripto yüklendi.")
    except Exception as e:
        print(f"   -> ⚠️ CMC Hatası: {e}")
    return data

# ==============================================================================
# 3. FONLAR (TEFAS FIX)
# ==============================================================================
def get_fon_metadata():
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    data = {}
    ICON_FUND = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/logos%2Ffon%2Ffon.png?alt=media&token=e3a51a80-b4d7-463d-8875-dca9b3addc82"
    
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Content-Type": "application/json"
    }
    
    try:
        simdi = datetime.now()
        tarih_str = simdi.strftime("%d.%m.%Y")
        payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
        
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        try:
            l = r.json().get('data', [])
        except:
            l = []

        if l:
            for f in l:
                # TEFAS HATASINI ENGELLEYEN KISIM:
                try:
                    kod = f.get('FONKODU')
                    isim = f.get('FONADI')
                    if kod and isim:
                        data[kod] = {"name": isim, "logo": ICON_FUND}
                except: continue
            print(f"   -> ✅ TEFAS: {len(data)} adet fon işlendi.")
            
    except Exception as e: 
        print(f"Hata (TEFAS): {e}")
    return data

# ==============================================================================
# 4. DÖVİZ & ALTIN
# ==============================================================================
def get_doviz_altin_metadata(): 
    print("--- LOGO/METADATA HAZIRLANIYOR (Döviz & Altın) ---")
    ICON_GOLD = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/logos%2Femtia%2Faltin.png?alt=media&token=fc20833e-acea-4580-8b1b-baf768ff1f24"
    ICON_METAL = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/logos%2Femtia%2Fgumus.png?alt=media&token=0938f6bd-9c56-4c64-ac5c-548e92dff1d3"

    doviz_config = {
        "USD": {"n": "ABD Doları", "c": "us"}, "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"}, "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "JPY": {"n": "Japon Yeni", "c": "jp"}, "CAD": {"n": "Kanada Doları", "c": "ca"},
        "AUD": {"n": "Avustralya Doları", "c": "au"}, "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "HKD": {"n": "Hong Kong Doları", "c": "hk"}, "RUB": {"n": "Rus Rublesi", "c": "ru"},
        "SEK": {"n": "İsveç Kronu", "c": "se"}, "NOK": {"n": "Norveç Kronu", "c": "no"},
        "DKK": {"n": "Danimarka Kronu", "c": "dk"}, "PLN": {"n": "Polonya Zlotisi", "c": "pl"},
        "HUF": {"n": "Macar Forinti", "c": "hu"}, "CZK": {"n": "Çek Korunası", "c": "cz"},
        "RON": {"n": "Rumen Leyi", "c": "ro"}, "BGN": {"n": "Bulgar Levası", "c": "bg"},
        "ISK": {"n": "İzlanda Kronu", "c": "is"}, "UAH": {"n": "Ukrayna Grivnası", "c": "ua"},
        "AZN": {"n": "Azerbaycan Manatı", "c": "az"}, "GEL": {"n": "Gürcistan Larisi", "c": "ge"},
        "TRY": {"n": "Türk Lirası", "c": "tr"}, "SAR": {"n": "Suudi Arabistan Riyali", "c": "sa"},
        "AED": {"n": "BAE Dirhemi", "c": "ae"}, "QAR": {"n": "Katar Riyali", "c": "qa"},
        "KWD": {"n": "Kuveyt Dinarı", "c": "kw"}, "BHD": {"n": "Bahreyn Dinarı", "c": "bh"},
        "OMR": {"n": "Umman Riyali", "c": "om"}, "JOD": {"n": "Ürdün Dinarı", "c": "jo"},
        "ILS": {"n": "İsrail Şekeli", "c": "il"}, "EGP": {"n": "Mısır Lirası", "c": "eg"},
        "MAD": {"n": "Fas Dirhemi", "c": "ma"}, "KRW": {"n": "Güney Kore Wonu", "c": "kr"},
        "SGD": {"n": "Singapur Doları", "c": "sg"}, "INR": {"n": "Hindistan Rupisi", "c": "in"},
        "IDR": {"n": "Endonezya Rupiahı", "c": "id"}, "MYR": {"n": "Malezya Ringgiti", "c": "my"},
        "PHP": {"n": "Filipin Pesosu", "c": "ph"}, "THB": {"n": "Tayland Bahtı", "c": "th"},
        "VND": {"n": "Vietnam Dongu", "c": "vn"}, "PKR": {"n": "Pakistan Rupisi", "c": "pk"},
        "KZT": {"n": "Kazakistan Tengesi", "c": "kz"}, "MXN": {"n": "Meksika Pesosu", "c": "mx"},
        "BRL": {"n": "Brezilya Reali", "c": "br"}, "ARS": {"n": "Arjantin Pesosu", "c": "ar"},
        "CLP": {"n": "Şili Pesosu", "c": "cl"}, "COP": {"n": "Kolombiya Pesosu", "c": "co"},
        "PEN": {"n": "Peru Solü", "c": "pe"}, "ZAR": {"n": "Güney Afrika Randı", "c": "za"}
    }
    data_doviz = {}
    for kod, info in doviz_config.items():
        data_doviz[kod] = {"name": info["n"], "logo": f"https://flagcdn.com/w320/{info['c']}.png"}
            
    altin_listesi = [
        "14 Ayar Bilezik", "18 Ayar Bilezik", "22 Ayar Bilezik", "Ata Altın", "Beşli Altın",
        "Cumhuriyet Altını", "Gram Altın", "Gram Gümüş", "Gram Has Altın", "Gram Paladyum",
        "Gram Platin", "Gremse Altın", "Hamit Altın", "Reşat Altın", "Tam Altın",
        "Yarım Altın", "Çeyrek Altın", "İkibuçuk Altın"
    ]
    data_altin = {}
    for isim in altin_listesi:
        ikon = ICON_METAL if any(x in isim for x in ["Gümüş", "Platin", "Paladyum"]) else ICON_GOLD
        data_altin[isim] = {"name": isim, "logo": ikon}
    
    return data_doviz, data_altin

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- LOGO/METADATA MİGRASYON BAŞLIYOR (FIREBASE STORAGE) ---")

    meta_kripto = get_crypto_metadata()
    meta_bist = get_tradingview_metadata("turkey")
    meta_abd = get_tradingview_metadata("america") 
    meta_fon = get_fon_metadata()
    meta_doviz, meta_altin = get_doviz_altin_metadata()

    # KAYIT İŞLEMLERİ (OTOMATİK PARÇALAMA DAHİL)
    coll_ref = db.collection(u'system_data')

    if meta_bist: 
        coll_ref.document(u'bist').set({u'data': meta_bist})
        print("✅ BIST veritabanı güncellendi.")
        
    # --- KRİTİK DEĞİŞİKLİK: ABD Hisseleri Parçalanıyor ---
    if meta_abd: 
        save_data_in_chunks(u'system_data', u'abd', meta_abd, chunk_size=2000)
    # ----------------------------------------------------
    
    if meta_kripto: 
        coll_ref.document(u'kripto').set({u'data': meta_kripto})
        print("✅ Kripto veritabanı güncellendi.")

    if meta_fon: 
        coll_ref.document(u'fon').set({u'data': meta_fon})
        print("✅ Fon veritabanı güncellendi.")
        
    if meta_doviz:
        coll_ref.document(u'doviz').set({u'data': meta_doviz})
        print("✅ Döviz veritabanı güncellendi.")
        
    if meta_altin:
        coll_ref.document(u'altin').set({u'data': meta_altin})
        print("✅ Altın veritabanı güncellendi.")

    print("\n🎉 TÜM İŞLEMLER BAŞARIYLA TAMAMLANDI!")
