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
import time

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
# YARDIMCI FONKSİYON: RESMİ STORAGE'A YÜKLE
# ==============================================================================
def upload_logo(original_url, file_name, folder_name):
    if not original_url: return None
    if "firebasestorage.googleapis.com" in original_url: return original_url
    
    try:
        resp = requests.get(original_url, headers=headers_general, timeout=10)
        if resp.status_code != 200: return original_url 

        content_type = resp.headers.get('Content-Type', '')
        file_data = resp.content
        
        if "svg" in content_type or original_url.endswith(".svg") or b"<svg" in file_data[:100]:
            extension = "svg"
            final_content_type = "image/svg+xml"
            blob_data = file_data
        else:
            img_bytes = io.BytesIO(file_data)
            try:
                img = Image.open(img_bytes)
                if img.mode != 'RGBA': img = img.convert('RGBA')
                img = img.resize((128, 128), Image.Resampling.LANCZOS)
                output_io = io.BytesIO()
                img.save(output_io, format='PNG', optimize=True)
                blob_data = output_io.getvalue()
                extension = "png"
                final_content_type = "image/png"
            except:
                return original_url 

        blob_path = f"logos/{folder_name}/{file_name}.{extension}"
        blob = bucket.blob(blob_path)
        
        new_token = str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": new_token}
        blob.upload_from_string(blob_data, content_type=final_content_type)
        
        encoded_path = blob_path.replace("/", "%2F") 
        download_url = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media&token={new_token}"
        return download_url

    except Exception as e:
        print(f"      Resim yükleme hatası ({file_name}): {e}")
        return original_url 

# ==============================================================================
# 1. ABD HİSSELERİ (Document: ABD) - Büyük harf
# ==============================================================================
def update_abd_smart():
    print("\n🇺🇸 1. ABD Hisseleri Kontrol Ediliyor (Document: ABD)...")
    
    live_ref = db.collection(u'market_data').document(u'LIVE_PRICES')
    # GÖRSELDEKİ İSİM: ABD (Büyük Harf)
    abd_ref = db.collection(u'system_data').document(u'ABD') 
    
    live_doc = live_ref.get()
    if not live_doc.exists: return
    
    target_symbols = list(live_doc.to_dict().get('borsa_abd_usd', {}).keys())
    # DÜZELTME: .get('data') kaldırıldı, direkt döküman okunuyor
    existing_data = abd_ref.get().to_dict() or {}
    
    missing_symbols = [s for s in target_symbols if s not in existing_data]
    if not missing_symbols:
        print("   ✅ Tüm ABD logoları güncel.")
        return

    print(f"   🔍 {len(missing_symbols)} eksik ABD hissesi aranıyor...")
    
    url = "https://scanner.tradingview.com/america/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "symbols": {"tickers": []},
        "columns": ["name", "description", "logoid"], 
        "range": [0, 6000]
    }
    
    tv_data_map = {}
    try:
        r = requests.post(url, json=payload, headers={"User-Agent": headers_general["User-Agent"]}, timeout=30)
        items = r.json().get('data', [])
        base_logo = "https://s3-symbol-logo.tradingview.com/"
        for h in items:
            d = h.get('d', [])
            sym = d[0]
            if sym in missing_symbols:
                logo_url = f"{base_logo}{d[2]}.svg" if d[2] else f"https://ui-avatars.com/api/?name={sym}&background=0D8ABC&color=fff"
                tv_data_map[sym] = {"name": d[1], "logo": logo_url}
    except Exception as e:
        print(f"   ⚠️ TradingView Hatası: {e}")

    updates = {}
    for sembol in missing_symbols:
        info = tv_data_map.get(sembol, {"name": sembol, "logo": f"https://ui-avatars.com/api/?name={sembol}&background=555&color=fff"})
        final_url = upload_logo(info['logo'], sembol, "stocks_america")
        updates[sembol] = {"name": info['name'], "logo": final_url}
        print(f"      📥 {sembol} yüklendi.")
        time.sleep(0.1)
        
    if updates:
        # DÜZELTME: Direkt merge=True ile 'data' wrapper olmadan basıyoruz
        abd_ref.set(updates, merge=True)
        print(f"   💾 ABD verileri güncellendi.")

# ==============================================================================
# 2. BIST HİSSELERİ (Document: bist) - Küçük harf
# ==============================================================================
def update_bist_smart():
    print("\n🇹🇷 2. BIST Hisseleri Kontrol Ediliyor (Document: bist)...")
    
    live_ref = db.collection(u'market_data').document(u'LIVE_PRICES')
    # GÖRSELDEKİ İSİM: bist (Küçük Harf)
    bist_ref = db.collection(u'system_data').document(u'bist')
    
    live_doc = live_ref.get()
    if not live_doc.exists: return

    target_symbols = list(live_doc.to_dict().get('borsa_tr', {}).keys())
    existing_data = bist_ref.get().to_dict() or {}
    
    missing_symbols = [s for s in target_symbols if s not in existing_data]
    if not missing_symbols:
        print("   ✅ Tüm BIST logoları güncel.")
        return

    print(f"   🔍 {len(missing_symbols)} eksik BIST hissesi aranıyor...")

    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "fund"]}],
        "columns": ["name", "description", "logoid"], 
        "range": [0, 1000]
    }

    tv_data_map = {}
    try:
        r = requests.post(url, json=payload, headers={"User-Agent": headers_general["User-Agent"]}, timeout=30)
        items = r.json().get('data', [])
        base_logo = "https://s3-symbol-logo.tradingview.com/"
        for h in items:
            d = h.get('d', [])
            sym = d[0]
            if sym in missing_symbols:
                logo_url = f"{base_logo}{d[2]}.svg" if d[2] else f"https://ui-avatars.com/api/?name={sym}&background=C8102E&color=fff"
                tv_data_map[sym] = {"name": d[1], "logo": logo_url}
    except Exception as e:
        print(f"   ⚠️ TradingView BIST Hatası: {e}")

    updates = {}
    for sembol in missing_symbols:
        info = tv_data_map.get(sembol, {"name": sembol, "logo": f"https://ui-avatars.com/api/?name={sembol}&background=C8102E&color=fff"})
        final_url = upload_logo(info['logo'], sembol, "bist")
        updates[sembol] = {"name": info['name'], "logo": final_url}
        print(f"      📥 {sembol} yüklendi.")
        time.sleep(0.1)

    if updates:
        bist_ref.set(updates, merge=True)
        print(f"   💾 BIST verileri güncellendi.")

# ==============================================================================
# 3. KRİPTO PARALAR (Document: kripto) - Küçük harf
# ==============================================================================
def update_crypto_smart():
    print("\n🚀 3. Kripto Paralar Kontrol Ediliyor (Document: kripto)...")
    
    if not CMC_API_KEY:
        print("   ⚠️ CMC_API_KEY eksik! Kripto güncellenemiyor.")
        return

    live_ref = db.collection(u'market_data').document(u'LIVE_PRICES')
    # GÖRSELDEKİ İSİM: kripto (Küçük Harf)
    crypto_ref = db.collection(u'system_data').document(u'kripto')
    
    live_doc = live_ref.get()
    target_symbols = list(live_doc.to_dict().get('kripto', {}).keys())
    existing_data = crypto_ref.get().to_dict() or {}
    
    missing_symbols = [s for s in target_symbols if s not in existing_data]
    if not missing_symbols:
        print("   ✅ Tüm Kripto logoları güncel.")
        return

    print(f"   🔍 {len(missing_symbols)} eksik kripto aranıyor...")

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"
    headers = { 'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json' }
    
    batch_size = 50
    updates = {}
    
    for i in range(0, len(missing_symbols), batch_size):
        batch = missing_symbols[i:i+batch_size]
        params = {'symbol': ','.join(batch)}
        
        try:
            r = requests.get(url, headers=headers, params=params)
            data = r.json().get('data', {})
            
            for sym, details in data.items():
                logo_raw = details.get('logo')
                name = details.get('name')
                if logo_raw:
                    final_url = upload_logo(logo_raw, sym, "crypto")
                    updates[sym] = {"name": name, "logo": final_url}
                    print(f"      📥 {sym} yüklendi.")
        except Exception as e:
            print(f"   ⚠️ CMC API Hatası: {e}")
            
    if updates:
        crypto_ref.set(updates, merge=True)
        print(f"   💾 Kripto verileri güncellendi.")

# ==============================================================================
# 4. DÖVİZ (Document: doviz) - Küçük harf
# Not: 'altin' belgesi de var ama kod mantığında doviz içine atıyoruz.
# Eğer altını ayırmak istersen aşağıyı bölebiliriz.
# ==============================================================================
def update_doviz_smart():
    print("\n💵 4. Döviz Kontrol Ediliyor (Document: doviz)...")
    
    live_ref = db.collection(u'market_data').document(u'LIVE_PRICES')
    # GÖRSELDEKİ İSİM: doviz (Küçük Harf)
    doviz_ref = db.collection(u'system_data').document(u'doviz')
    
    live_doc = live_ref.get()
    target_symbols = list(live_doc.to_dict().get('doviz', {}).keys())
    existing_data = doviz_ref.get().to_dict() or {}
    
    missing_symbols = [s for s in target_symbols if s not in existing_data]
    if not missing_symbols:
        print("   ✅ Tüm Döviz logoları güncel.")
        return

    currency_map = {
        "USD": "us", "EUR": "eu", "GBP": "gb", "CHF": "ch", 
        "CAD": "ca", "AUD": "au", "JPY": "jp", "CNY": "cn",
        "RUB": "ru", "AZN": "az", "SAR": "sa"
    }
    
    updates = {}
    for sembol in missing_symbols:
        country_code = currency_map.get(sembol)
        
        if country_code:
            raw_url = f"https://flagcdn.com/w320/{country_code}.png"
            name = f"{sembol} / TRY"
        elif sembol in ["GA", "GRAMALTIN", "ALTIN", "ONS"]:
            # Altınları da şimdilik doviz içine atıyoruz.
            raw_url = f"https://ui-avatars.com/api/?name=Au&background=FFD700&color=fff&size=128"
            name = "Gram Altın"
        else:
            raw_url = f"https://ui-avatars.com/api/?name={sembol[:2]}&background=222&color=fff"
            name = sembol

        final_url = upload_logo(raw_url, sembol, "currencies")
        updates[sembol] = {"name": name, "logo": final_url}
        print(f"      📥 {sembol} yüklendi.")
        
    if updates:
        doviz_ref.set(updates, merge=True)
        print(f"   💾 Döviz verileri güncellendi.")

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- VARIO LOGO SENKRONİZASYON BOTU (FIREBASE FIX) ---")
    update_abd_smart()
    update_bist_smart()
    update_crypto_smart()
    update_doviz_smart()
    print("\n🎉 TÜM İŞLEMLER TAMAMLANDI!")
