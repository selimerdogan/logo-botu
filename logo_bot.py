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
BUCKET_NAME = "vario-264d9.firebasestorage.app" # Bucket adın

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
    # Eğer zaten bizim storage linkimizse veya geçersizse elleme
    if "firebasestorage.googleapis.com" in original_url: return original_url
    if not original_url or "ui-avatars.com" in original_url: return original_url

    try:
        resp = requests.get(original_url, headers=headers_general, timeout=10)
        if resp.status_code != 200: return original_url 

        content_type = resp.headers.get('Content-Type', '')
        file_data = resp.content
        
        # SVG Kontrolü
        if "svg" in content_type or original_url.endswith(".svg") or b"<svg" in file_data[:100]:
            extension = "svg"
            final_content_type = "image/svg+xml"
            blob_data = file_data
        else:
            # PNG/JPG ise optimize et (128x128 PNG)
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
                return original_url # İşleyemezsek orijinal URL kalsın

        # Storage Yolu: logos/stocks_america/AAPL.png gibi
        blob_path = f"logos/{folder_name}/{file_name}.{extension}"
        blob = bucket.blob(blob_path)
        
        # Public Token Oluştur
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
# 1. ABD HİSSELERİ (AKILLI GÜNCELLEME - TEK DOSYA)
# ==============================================================================
def update_abd_smart():
    print("1. ABD Hisseleri Kontrol Ediliyor (system_data/ABD)...")
    
    # ADIM A: Canlı Veriden Listeyi Al
    live_ref = db.collection(u'market_data').document(u'LIVE_PRICES')
    live_doc = live_ref.get()
    
    if not live_doc.exists:
        print("   ⚠️ HATA: Canlı veri (LIVE_PRICES) bulunamadı. Önce market botu çalışmalı.")
        return

    # Canlıdaki hisse sembollerini al (Örn: AAPL, TSLA, NVDA...)
    live_data = live_doc.to_dict().get('borsa_abd_usd', {})
    target_symbols = list(live_data.keys())
    print(f"   📋 Canlı listede {len(target_symbols)} adet hisse var.")

    # ADIM B: Mevcut 'ABD' Dosyasını Oku
    # Artık abd_1, abd_2 yok. Tek dosya: system_data/ABD
    abd_ref = db.collection(u'system_data').document(u'ABD')
    abd_doc = abd_ref.get()
    
    existing_data = {}
    if abd_doc.exists:
        existing_data = abd_doc.to_dict().get('data', {})
        print(f"   💾 Havuzda kayıtlı {len(existing_data)} hisse var.")
    else:
        print("   🆕 'ABD' dosyası ilk kez oluşturulacak.")

    # ADIM C: Eksikleri Belirle
    missing_symbols = [s for s in target_symbols if s not in existing_data]
    
    if not missing_symbols:
        print("   ✅ Tüm canlı hisselerin logosu zaten mevcut. İşlem yok.")
        return

    print(f"   🔍 {len(missing_symbols)} adet eksik logo tespit edildi. TradingView taranıyor...")

    # ADIM D: TradingView'dan Veri Çek
    # Eksikleri bulmak için TV'den geniş bir liste çekiyoruz
    url = "https://scanner.tradingview.com/america/scan"
    headers_tv = {
        "User-Agent": headers_general["User-Agent"],
        "Content-Type": "application/json"
    }
    payload = {
        "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "description", "logoid"], 
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 4000] # İlk 4000 hisse içinde arayalım
    }

    tv_data_map = {}
    try:
        r = requests.post(url, json=payload, headers=headers_tv, timeout=30)
        items = r.json().get('data', [])
        base_logo_url = "https://s3-symbol-logo.tradingview.com/"
        
        for h in items:
            d = h.get('d', [])
            if len(d) > 2:
                sym = d[0]      # Sembol
                desc = d[1]     # İsim
                lid = d[2]      # Logo ID
                
                # Sadece eksik listesindeyse alalım
                if sym in missing_symbols:
                    if lid:
                        raw_url = f"{base_logo_url}{lid}.svg"
                    else:
                        # Logosu yoksa UI Avatars (Renkli Harf)
                        raw_url = f"https://ui-avatars.com/api/?name={sym}&background=0D8ABC&color=fff&size=128&bold=true"
                    
                    tv_data_map[sym] = {"name": desc, "raw_logo": raw_url}

    except Exception as e:
        print(f"   ⚠️ TradingView Bağlantı Hatası: {e}")
        return

    # ADIM E: Eksikleri Yükle ve Kaydet
    updated_count = 0
    
    for sembol in missing_symbols:
        # TradingView'da bulduysak bilgilerini al, bulamadıysak varsayılan oluştur
        if sembol in tv_data_map:
            info = tv_data_map[sembol]
            raw_url = info['raw_logo']
            name = info['name']
        else:
            # Listede yoksa bile boş geçmeyelim, harf logosu yapalım
            raw_url = f"https://ui-avatars.com/api/?name={sembol}&background=555&color=fff&size=128&bold=true"
            name = sembol 

        print(f"      📥 Yükleniyor: {sembol} ...", end="")
        
        # --- STORAGE YOLU: stocks_america ---
        final_logo_url = upload_logo(raw_url, sembol, "stocks_america")
        
        # Veritabanı formatına ekle
        existing_data[sembol] = {
            "name": name,
            "logo": final_logo_url
        }
        updated_count += 1
        print(" Tamam.")
        
        # Çok hızlı istek atıp banlanmamak için minik bekleme
        time.sleep(0.1)

    # ADIM F: Sonucu Kaydet (system_data/ABD)
    if updated_count > 0:
        abd_ref.set({'data': existing_data}, merge=True)
        print(f"   💾 'ABD' dosyası güncellendi. {updated_count} yeni logo eklendi.")
    else:
        print("   ℹ️ Eklenecek veri bulunamadı.")

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- LOGO BOTU (V3 - Single Doc / Stocks America) ---")

    # 1. ABD Hisselerini Güncelle
    update_abd_smart()

    # İstersen Kripto vb. fonksiyonları buraya ekleyebilirsin.
    # update_crypto...
    # update_fon...

    print("\n🎉 İŞLEMLER TAMAMLANDI!")
