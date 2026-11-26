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
    if not original_url:
        return None
    # Sahte ui-avatars.com linklerini reddet
    if "ui-avatars.com" in original_url:
        return None
    if "firebasestorage.googleapis.com" in original_url:
        return original_url
    
    try:
        resp = requests.get(original_url, headers=headers_general, timeout=12)
        if resp.status_code != 200 or len(resp.content) < 50:
            return None 

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
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                img = img.resize((128, 128), Image.Resampling.LANCZOS)
                output_io = io.BytesIO()
                img.save(output_io, format='PNG', optimize=True)
                blob_data = output_io.getvalue()
                extension = "png"
                final_content_type = "image/png"
            except Exception as e:
                print(f"      Görsel işleme hatası ({file_name}): {e}")
                return None

        clean_name = file_name.replace("/", "_").replace(" ", "_")
        blob_path = f"logos/{folder_name}/{clean_name}.{extension}"
        blob = bucket.blob(blob_path)
        
        new_token = str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": new_token}
        blob.upload_from_string(blob_data, content_type=final_content_type)
        
        encoded_path = blob_path.replace("/", "%2F") 
        download_url = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media&token={new_token}"
        return download_url

    except Exception as e:
        print(f"      Resim yükleme hatası ({file_name}): {e}")
        return None

# ==============================================================================
# 1. TEFAS FONLARI (Document: fon, Folder: logos/fon)
# Türkiye'deki ~45 Portföy Yönetim Şirketinin (PYŞ) resmi logolarını eşler
# ==============================================================================
PYS_LOGOS = {
    "AK": {"name": "Ak Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Akbank_logo.svg/320px-Akbank_logo.svg.png"},
    "İŞ": {"name": "İş Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Türkiye_İş_Bankası_logo.svg/320px-Türkiye_İş_Bankası_logo.svg.png"},
    "YAPI KREDİ": {"name": "Yapı Kredi Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Yapı_Kredi_logo.svg/320px-Yapı_Kredi_logo.svg.png"},
    "GARANTİ": {"name": "Garanti BBVA Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Garanti_BBVA_logo.svg/320px-Garanti_BBVA_logo.svg.png"},
    "ZİRAAT": {"name": "Ziraat Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Ziraat_Bankası_logo.svg/320px-Ziraat_Bankası_logo.svg.png"},
    "VAKIF": {"name": "Vakıf Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/aa/VakıfBank_logo.svg/320px-VakıfBank_logo.svg.png"},
    "HALK": {"name": "Halk Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Halkbank_logo.svg/320px-Halkbank_logo.svg.png"},
    "TEB": {"name": "TEB Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Türk_Ekonomi_Bankası_logo.svg/320px-Türk_Ekonomi_Bankası_logo.svg.png"},
    "QNB": {"name": "QNB Finans Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/QNB_Finansbank_logo.svg/320px-QNB_Finansbank_logo.svg.png"},
    "DENİZ": {"name": "Deniz Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/DenizBank_logo.svg/320px-DenizBank_logo.svg.png"},
    "FİBA": {"name": "Fiba Portföy", "logo": "https://fibaportfoy.com.tr/assets/img/logo.png"},
    "RE-PİE": {"name": "Re-Pie Portföy", "logo": "https://re-pie.com/assets/img/re-pie-logo.png"},
    "PARDUS": {"name": "Pardus Portföy", "logo": "https://pardusportfoy.com/assets/images/logo.png"},
    "AZİMUT": {"name": "Azimut Portföy", "logo": "https://www.azimutportfoy.com/images/logo.png"},
    "MARMARA": {"name": "Marmara Capital", "logo": "https://marmaracapital.com/wp-content/uploads/2019/04/logo.png"},
    "TÜRKİYE HAYAT": {"name": "Türkiye Hayat Emeklilik", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Türkiye_Sigorta_logo.svg/320px-Türkiye_Sigorta_logo.svg.png"},
    "TACİRLER": {"name": "Tacirler Portföy", "logo": "https://www.tacirler.com.tr/assets/images/logo.png"},
    "İSTANBUL PORTFÖY": {"name": "İstanbul Portföy", "logo": "https://www.istanbulportfoy.com/assets/images/logo.png"},
    "INVEO": {"name": "Inveo Portföy", "logo": "https://www.inveoportfoy.com/assets/images/logo.png"},
    "A1": {"name": "A1 Portföy", "logo": "https://www.a1portfoy.com.tr/assets/images/logo.png"},
    "TERA": {"name": "Tera Portföy", "logo": "https://teraportfoy.com/assets/images/logo.png"},
    "NEO": {"name": "Neo Portföy", "logo": "https://www.neoportfoy.com/assets/images/logo.png"},
    "GEDİK": {"name": "Gedik Portföy", "logo": "https://www.gedik.com/assets/images/gedik-logo.svg"},
    "GLOBAL": {"name": "Global Portföy", "logo": "https://www.globalportfoy.com.tr/assets/img/logo.png"},
    "ALBARAKA": {"name": "Albaraka Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Albaraka_Türk_logo.svg/320px-Albaraka_Türk_logo.svg.png"},
    "KUVEYT": {"name": "KT Portföy", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Kuveyt_Türk_logo.svg/320px-Kuveyt_Türk_logo.svg.png"},
    "ÜNLÜ": {"name": "Ünlü Portföy", "logo": "https://unluportfoy.com/assets/images/logo.png"},
    "ROTA": {"name": "Rota Portföy", "logo": "https://rotaportfoy.com.tr/assets/images/logo.png"},
    "HEDEF": {"name": "Hedef Portföy", "logo": "https://hedefportfoy.com.tr/assets/images/logo.png"},
    "ATLAS": {"name": "Atlas Portföy", "logo": "https://www.atlasportfoy.com.tr/assets/images/logo.png"},
    "BV": {"name": "BV Portföy", "logo": "https://bvportfoy.com/assets/images/logo.png"},
    "OSMANLI": {"name": "Osmanlı Portföy", "logo": "https://www.osmanlimenkul.com.tr/assets/images/logo.png"},
    "PHILLIP": {"name": "PhillipCapital Portföy", "logo": "https://www.phillipcapital.com.tr/assets/images/logo.png"},
    "ALLIANZ": {"name": "Allianz Yaşam ve Emeklilik", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Allianz_logo.svg/320px-Allianz_logo.svg.png"},
    "ANADOLU HAYAT": {"name": "Anadolu Hayat Emeklilik", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/Anadolu_Hayat_Emeklilik_logo.svg/320px-Anadolu_Hayat_Emeklilik_logo.svg.png"},
    "AGESA": {"name": "AgeSA Hayat ve Emeklilik", "logo": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/AgeSA_logo.svg/320px-AgeSA_logo.svg.png"},
    "KATILIM EMEKLİLİK": {"name": "Katılım Emeklilik", "logo": "https://www.katilimemeklilik.com.tr/assets/images/logo.png"},
    "OYAK": {"name": "Oyak Portföy", "logo": "https://www.oyakportfoy.com.tr/assets/images/logo.png"},
    "BULLS": {"name": "Bulls Portföy", "logo": "https://www.bullsportfoy.com.tr/assets/images/logo.png"},
    "DİNAMİK": {"name": "Dinamik Portföy", "logo": "https://dinamikportfoy.com/assets/images/logo.png"},
    "ATA": {"name": "Ata Portföy", "logo": "https://ataportfoy.com.tr/assets/images/logo.png"},
    "COLENDI": {"name": "Colendi Portföy", "logo": "https://colendi.com/assets/images/logo.png"}
}

def update_fon_smart():
    print("\n🏛️ 1. TEFAS Fonları Kurucu PYŞ Logoları Eşleniyor (Document: fon)...")
    live_ref = db.collection('market_data').document('LIVE_PRICES')
    fon_ref = db.collection('system_data').document('fon')
    
    live_doc = live_ref.get()
    if not live_doc.exists:
        print("   ⚠️ LIVE_PRICES bulunamadı!")
        return
        
    funds = live_doc.to_dict().get('fon_tl', {})
    if not funds:
        print("   ⚠️ LIVE_PRICES içinde fon_tl bulunamadı!")
        return

    # Önce PYŞ logolarını Storage'a yükleyelim
    uploaded_pys_logos = {}
    for pys_key, info in PYS_LOGOS.items():
        clean_key = pys_key.lower().replace(" ", "_").replace("ı", "i").replace("ş", "s").replace("ü", "u").replace("ö", "o").replace("ç", "c").replace("ğ", "g")
        url = upload_logo(info["logo"], clean_key, "fon")
        if url:
            uploaded_pys_logos[pys_key] = url

    print(f"   ✅ {len(uploaded_pys_logos)} adet kurumsal PYŞ logosu hazırlandı.")

    # 1.400 fonu kurucusuyla eşle
    existing_data = fon_ref.get().to_dict() or {}
    updates = {}
    
    default_fon_logo = uploaded_pys_logos.get("İŞ") or list(uploaded_pys_logos.values())[0] if uploaded_pys_logos else None

    for kod, f_info in funds.items():
        title = (f_info.get('name') or '').upper().replace("İ", "I")
        matched_logo = None
        matched_pys_name = f_info.get('name', kod)

        for pys_key, logo_url in uploaded_pys_logos.items():
            norm_key = pys_key.upper().replace("İ", "I")
            if norm_key in title:
                matched_logo = logo_url
                matched_pys_name = PYS_LOGOS[pys_key]["name"]
                break

        if not matched_logo:
            matched_logo = default_fon_logo

        # Mevcut veride yoksa veya güncellenmesi gerekiyorsa
        if kod not in existing_data or not existing_data[kod].get('logo') or "ui-avatars" in existing_data[kod].get('logo', ''):
            updates[kod] = {
                "name": f_info.get('name') or matched_pys_name,
                "logo": matched_logo
            }

    if updates:
        # Firestore 500'erli batch'lerle yaz
        batch_size = 400
        items = list(updates.items())
        for i in range(0, len(items), batch_size):
            slice_dict = dict(items[i:i+batch_size])
            fon_ref.set(slice_dict, merge=True)
            print(f"   💾 {len(slice_dict)} fon logosu güncellendi ({i + len(slice_dict)}/{len(items)})...")
        print(f"   🎉 Toplam {len(updates)} TEFAS fonu kurumsal logolarıyla eşlendi.")
    else:
        print("   ✅ Tüm TEFAS fon logoları zaten güncel.")

# ==============================================================================
# 2. ABD HİSSELERİ (Document: ABD, Folder: logos/abd)
# TradingView Scanner + Google Finance / Clearbit CDN ile gerçek logolar
# ==============================================================================
def update_abd_smart():
    print("\n🇺🇸 2. ABD Hisseleri Taranıyor (Document: ABD)...")
    live_ref = db.collection('market_data').document('LIVE_PRICES')
    abd_ref = db.collection('system_data').document('ABD') 
    
    live_doc = live_ref.get()
    if not live_doc.exists: return
    
    target_symbols = list(live_doc.to_dict().get('borsa_abd_usd', {}).keys())
    existing_data = abd_ref.get().to_dict() or {}
    
    # Eksik olan, sahte ui-avatars veya eski stocks_america klasöründe kalanları tespit et
    missing_symbols = [
        s for s in target_symbols 
        if s not in existing_data 
        or not existing_data[s].get('logo') 
        or "ui-avatars.com" in existing_data[s].get('logo', '')
        or "stocks_america" in existing_data[s].get('logo', '')
    ]
    
    if not missing_symbols:
        print("   ✅ Tüm ABD logoları güncel ve gerçek logolarla eşli.")
        return

    print(f"   🔍 {len(missing_symbols)} eksik/hatalı ABD hissesi taranıyor...")
    
    url = "https://scanner.tradingview.com/america/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "symbols": {"tickers": []},
        "columns": ["name", "description", "logoid"], 
        "range": [0, 8000]
    }
    
    tv_data_map = {}
    try:
        r = requests.post(url, json=payload, headers={"User-Agent": headers_general["User-Agent"]}, timeout=30)
        items = r.json().get('data', [])
        base_logo = "https://s3-symbol-logo.tradingview.com/"
        for h in items:
            d = h.get('d', [])
            sym = d[0]
            if sym in missing_symbols and d[2]:
                tv_data_map[sym] = {"name": d[1], "logo": f"{base_logo}{d[2]}.svg"}
    except Exception as e:
        print(f"   ⚠️ TradingView Hatası: {e}")

    updates = {}
    for sembol in missing_symbols:
        # TradingView'de yoksa Google Favicon veya Logo CDN dene
        logo_candidate = None
        comp_name = sembol
        
        if sembol in tv_data_map:
            logo_candidate = tv_data_map[sembol]["logo"]
            comp_name = tv_data_map[sembol]["name"]
        else:
            # Yedek kurumsal CDN'ler (FinancialModelingPrep / Logo Dev)
            logo_candidate = f"https://financialmodelingprep.com/image-stock/{sembol}.png"

        final_url = upload_logo(logo_candidate, sembol, "abd")
        if final_url:
            updates[sembol] = {"name": comp_name, "logo": final_url}
            print(f"      📥 {sembol} -> {final_url[:60]}...")
            time.sleep(0.08)
        
    if updates:
        batch_size = 350
        items = list(updates.items())
        for i in range(0, len(items), batch_size):
            slice_dict = dict(items[i:i+batch_size])
            abd_ref.set(slice_dict, merge=True)
        print(f"   💾 {len(updates)} ABD hissesi gerçek logolarla güncellendi.")

# ==============================================================================
# 3. BIST HİSSELERİ (Document: bist, Folder: logos/bist)
# ==============================================================================
def update_bist_smart():
    print("\n🇹🇷 3. BIST Hisseleri Taranıyor (Document: bist)...")
    live_ref = db.collection('market_data').document('LIVE_PRICES')
    bist_ref = db.collection('system_data').document('bist')
    
    live_doc = live_ref.get()
    if not live_doc.exists: return

    target_symbols = list(live_doc.to_dict().get('borsa_tr_tl', {}).keys())
    existing_data = bist_ref.get().to_dict() or {}
    
    # BIST Özel Alan Adları (TradingView'de henüz SVG'si olmayan yeni/özel hisseler için)
    BIST_DOMAINS = {
        "KARCL": "kardemircelik.com.tr",
        "ISVEA": "isvea.com.tr",
        "KPEKS": "kapeks.com.tr",
        "EBEBK": "ebebek.com",
        "SURGY": "surtatil.com",
        "MEKAG": "mekaglobal.com",
        "TABGD": "tabgida.com.tr",
        "VRGYO": "veragyo.com.tr",
        "MHRGY": "mhrgyo.com.tr",
        "BORLS": "borlease.com.tr",
        "DOFRY": "dofer.com.tr",
        "MARBL": "turaclar.com",
        "GZNMI": "gezinomi.com"
    }

    missing_symbols = [
        s for s in target_symbols 
        if s not in existing_data 
        or not existing_data[s].get('logo') 
        or "ui-avatars.com" in existing_data[s].get('logo', '')
        or "stocks_turkey" in existing_data[s].get('logo', '')
    ]
    
    if not missing_symbols:
        print("   ✅ Tüm BIST logoları güncel.")
        return

    print(f"   🔍 {len(missing_symbols)} eksik/hatalı BIST hissesi taranıyor...")

    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "fund"]}],
        "columns": ["name", "description", "logoid"], 
        "range": [0, 1000]
    }

    tv_data_map = {}
    try:
        r = requests.post(url, json=payload, headers={"User-Agent": headers_general["User-Agent"]}, timeout=25)
        items = r.json().get('data', [])
        base_logo = "https://s3-symbol-logo.tradingview.com/"
        for h in items:
            d = h.get('d', [])
            sym = d[0]
            if sym in missing_symbols and d[2]:
                tv_data_map[sym] = {"name": d[1], "logo": f"{base_logo}{d[2]}.svg"}
    except Exception as e:
        print(f"   ⚠️ TradingView BIST Hatası: {e}")

    updates = {}
    for sembol in missing_symbols:
        logo_candidate = None
        comp_name = sembol
        if sembol in tv_data_map:
            logo_candidate = tv_data_map[sembol]["logo"]
            comp_name = tv_data_map[sembol]["name"]
        elif sembol in BIST_DOMAINS:
            logo_candidate = f"https://www.google.com/s2/favicons?domain={BIST_DOMAINS[sembol]}&sz=128"
        else:
            # Alternatif BIST logo CDN
            logo_candidate = f"https://fintables.com/logos/{sembol}.png"

        final_url = upload_logo(logo_candidate, sembol, "bist")
        if final_url:
            updates[sembol] = {"name": comp_name, "logo": final_url}
            print(f"      📥 {sembol} yüklendi.")
            time.sleep(0.08)

    if updates:
        bist_ref.set(updates, merge=True)
        print(f"   💾 {len(updates)} BIST hissesi güncellendi.")

# ==============================================================================
# 4. KRİPTO PARALAR (Document: kripto, Folder: logos/crypto)
# ==============================================================================
def update_crypto_smart():
    print("\n🚀 4. Kripto Paralar Kontrol Ediliyor (Document: kripto)...")
    if not CMC_API_KEY:
        print("   ⚠️ CMC_API_KEY eksik! Kripto logoları atlanıyor.")
        return

    live_ref = db.collection('market_data').document('LIVE_PRICES')
    crypto_ref = db.collection('system_data').document('kripto')
    
    live_doc = live_ref.get()
    target_symbols_raw = list(live_doc.to_dict().get('kripto_usd', {}).keys())
    existing_data = crypto_ref.get().to_dict() or {}
    
    missing_keys = [
        s for s in target_symbols_raw 
        if s not in existing_data or not existing_data[s].get('logo') or "ui-avatars.com" in existing_data[s].get('logo', '')
    ]
    
    if not missing_keys:
        print("   ✅ Tüm Kripto logoları güncel.")
        return

    print(f"   🔍 {len(missing_keys)} eksik kripto aranıyor...")

    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"
    headers = { 'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json' }
    
    batch_size = 50
    updates = {}
    
    for i in range(0, len(missing_keys), batch_size):
        batch_keys = missing_keys[i:i+batch_size]
        clean_symbols_map = {k: k.replace("-USD", "") for k in batch_keys}
        clean_symbols_list = list(clean_symbols_map.values())
        
        try:
            r = requests.get(url, headers=headers, params={'symbol': ','.join(clean_symbols_list)}, timeout=20)
            data = r.json().get('data', {})
            
            for clean_sym, details in data.items():
                original_key = next((k for k, v in clean_symbols_map.items() if v == clean_sym), None)
                if original_key and details.get('logo'):
                    logo_raw = details.get('logo')
                    name = details.get('name')
                    final_url = upload_logo(logo_raw, clean_sym, "crypto")
                    if final_url:
                        updates[original_key] = {"name": name, "logo": final_url}
                        print(f"      📥 {original_key} yüklendi.")
        except Exception as e:
            print(f"   ⚠️ CMC API Hatası: {e}")

        # CMC'de bulunamayanlar için CoinGecko yedek araması
        for original_key, clean_sym in clean_symbols_map.items():
            if original_key not in updates:
                try:
                    cg_r = requests.get(f"https://api.coingecko.com/api/v3/search?query={clean_sym}", headers=headers_general, timeout=8)
                    if cg_r.status_code == 200:
                        coins = cg_r.json().get('coins', [])
                        for c in coins:
                            if c.get('symbol', '').upper() == clean_sym.upper():
                                cg_logo = c.get('large')
                                if cg_logo:
                                    final_url = upload_logo(cg_logo, clean_sym, "crypto")
                                    if final_url:
                                        updates[original_key] = {"name": c.get('name', clean_sym), "logo": final_url}
                                        print(f"      📥 [CoinGecko] {original_key} yüklendi.")
                                        break
                except Exception:
                    pass
            
    if updates:
        crypto_ref.set(updates, merge=True)
        print(f"   💾 {len(updates)} Kripto logosu güncellendi.")

# ==============================================================================
# 5. DÖVİZ & EMTİA (Document: doviz & altin, Folder: logos/doviz & logos/emtia)
# ==============================================================================
def update_doviz_smart():
    print("\n💵 5. Döviz & Emtia Kontrol Ediliyor (Document: doviz & altin)...")
    doviz_ref = db.collection('system_data').document('doviz')
    altin_ref = db.collection('system_data').document('altin')

    currency_map = {
        "USD": "us", "EUR": "eu", "GBP": "gb", "CHF": "ch", 
        "CAD": "ca", "AUD": "au", "JPY": "jp", "CNY": "cn",
        "RUB": "ru", "AZN": "az", "SAR": "sa", "KWD": "kw",
        "AED": "ae", "QAR": "qa", "NOK": "no", "SEK": "se", "DKK": "dk"
    }

    updates = {}
    for sembol, country_code in currency_map.items():
        raw_url = f"https://flagcdn.com/w320/{country_code}.png"
        final_url = upload_logo(raw_url, sembol, "doviz")
        if final_url:
            updates[sembol] = {"name": f"{sembol} / TRY", "logo": final_url}

    if updates:
        doviz_ref.set(updates, merge=True)
        print(f"   💾 {len(updates)} Döviz bayrak logosu güncellendi.")

    # Emtia Logoları (Altın, Gümüş, Platin, Paladyum)
    altin_logos = {
        "Gram Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Gram Has Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Çeyrek Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Yarım Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Tam Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Cumhuriyet Altını": "https://img.icons8.com/color/144/gold-bars.png",
        "Ata Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Beşli Altın": "https://img.icons8.com/color/144/gold-bars.png",
        "Gram Gümüş": "https://img.icons8.com/color/144/silver-bars.png",
        "Gümüş": "https://img.icons8.com/color/144/silver-bars.png",
        "Gram Platin": "https://img.icons8.com/fluency/144/metal.png",
        "Gram Paladyum": "https://img.icons8.com/fluency/144/metal.png"
    }
    altin_updates = {}
    for sembol, url in altin_logos.items():
        clean_name = sembol.lower().replace(" ", "_").replace("ı", "i").replace("ü", "u")
        final_url = upload_logo(url, clean_name, "emtia")
        if final_url:
            altin_updates[sembol] = {"name": sembol, "logo": final_url}

    if altin_updates:
        altin_ref.set(altin_updates, merge=True)
        print(f"   💾 {len(altin_updates)} Emtia logosu güncellendi.")

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- 🎨 VARIO AKILLI LOGO SENKRONİZASYON & ONARIM MOTORU ---")
    update_fon_smart()
    update_abd_smart()
    update_bist_smart()
    update_crypto_smart()
    update_doviz_smart()
    print("\n🎉 TÜM LOGOLAR RESMİ VE KURUMSAL KAYNAKLARDAN EŞLENDİ!")
