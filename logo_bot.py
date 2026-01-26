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
# SADECE ÖZEL LİSTE İÇİN LOGO GÜNCELLEME (system_data/kripto)
# ==============================================================================
def sync_manual_crypto_logos():
    print("\n🚀 Özel Liste Kripto Logoları Kontrol Ediliyor...")
    
    if not CMC_API_KEY:
        print("   ⚠️ CMC_API_KEY eksik! İşlem yapılamıyor.")
        return

    # --- SADECE BU COINLER İŞLENECEK ---
    MANUAL_COINS = [
        "import requests
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
# SADECE ÖZEL LİSTE İÇİN LOGO GÜNCELLEME (system_data/kripto)
# ==============================================================================
def sync_manual_crypto_logos():
    print("\n🚀 Özel Liste Kripto Logoları Kontrol Ediliyor...")
    
    if not CMC_API_KEY:
        print("   ⚠️ CMC_API_KEY eksik! İşlem yapılamıyor.")
        return

    # --- SADECE BU COINLER İŞLENECEK ---
    MANUAL_COINS = [
        "LISUSD", "SKR", "GOHOME", "GOOGLon", 
        "BUSD", "vBUSD", "USDon"
    ]
    # -----------------------------------

    # Hedef: system_data -> kripto
    crypto_ref = db.collection(u'system_data').document(u'kripto')
    
    # Mevcut veriyi çek (Silmemek için)
    existing_data = crypto_ref.get().to_dict() or {}
    
    # Hangi formatta kaydedeceğiz? -> "SYMBOL-USD"
    target_keys = [f"{s}-USD" for s in MANUAL_COINS]
    
    # Sadece system_data'da EKSİK olanları veya listedekileri tarayalım
    # İsteğe göre: Hepsini tekrar taramak garanti olur.
    missing_in_db = [k for k in target_keys if k not in existing_data]
    
    if not missing_in_db:
        print("   ✅ Listedeki tüm coinlerin logoları zaten sistemde var.")
        # Yine de güncellemek istersen burayı comment'e alabilirsin.
        return

    print(f"   🔍 {len(missing_in_db)} adet yeni coinin logosu aranıyor...")

    # CoinMarketCap Metadata Endpoint
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"
    headers = { 'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json' }
    
    updates = {}
    batch_size = 50
    
    # Eksik olanları işle
    for i in range(0, len(missing_in_db), batch_size):
        batch_keys = missing_in_db[i:i+batch_size]
        
        # CMC'ye sorarken "-USD" kısmını siliyoruz (TAIKO-USD -> TAIKO)
        clean_symbols_map = {k: k.replace("-USD", "") for k in batch_keys}
        clean_symbols_list = list(clean_symbols_map.values())
        
        params = {'symbol': ','.join(clean_symbols_list)}
        
        try:
            r = requests.get(url, headers=headers, params=params)
            data = r.json().get('data', {})
            
            for clean_sym, details in data.items():
                # Orijinal anahtarı (TAIKO-USD) bul
                original_key = next((k for k, v in clean_symbols_map.items() if v == clean_sym), None)
                
                if original_key and details.get('logo'):
                    logo_raw = details.get('logo')
                    name = details.get('name')
                    
                    # Logoyu indir ve Firebase Storage'a yükle
                    final_url = upload_logo(logo_raw, clean_sym, "crypto")
                    
                    # Güncelleme listesine ekle
                    updates[original_key] = {"name": name, "logo": final_url}
                    print(f"      📥 {original_key} ({name}) logosu hazırlandı.")
            
        except Exception as e:
            print(f"   ⚠️ CMC API Hatası: {e}")
            
    # Sadece yeni bulunanları MEVCUT verinin üzerine ekle (Merge)
    if updates:
        crypto_ref.set(updates, merge=True)
        print(f"   💾 {len(updates)} adet yeni logo system_data/kripto dosyasına eklendi.")
    else:
        print("   ℹ️ Eklenecek yeni logo bulunamadı.")

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- ÖZEL MANUEL LOGO YÜKLEYİCİ ---")
    
    # Sadece kripto fonksiyonunu çalıştırıyoruz.
    sync_manual_crypto_logos()
    
    print("\n🎉 İŞLEM TAMAMLANDI!")", "LSK", "SKR", "RESOLV", "UB", "TAIKO", "GWEI", "EUL", 
        "KLK", "FB", "LisUSD", "ICNT", "GOHOME", "GOOGLON", "UCN", 
        "BUSD", "vBUSD"
    ]
    # -----------------------------------

    # Hedef: system_data -> kripto
    crypto_ref = db.collection(u'system_data').document(u'kripto')
    
    # Mevcut veriyi çek (Silmemek için)
    existing_data = crypto_ref.get().to_dict() or {}
    
    # Hangi formatta kaydedeceğiz? -> "SYMBOL-USD"
    target_keys = [f"{s}-USD" for s in MANUAL_COINS]
    
    # Sadece system_data'da EKSİK olanları veya listedekileri tarayalım
    # İsteğe göre: Hepsini tekrar taramak garanti olur.
    missing_in_db = [k for k in target_keys if k not in existing_data]
    
    if not missing_in_db:
        print("   ✅ Listedeki tüm coinlerin logoları zaten sistemde var.")
        # Yine de güncellemek istersen burayı comment'e alabilirsin.
        return

    print(f"   🔍 {len(missing_in_db)} adet yeni coinin logosu aranıyor...")

    # CoinMarketCap Metadata Endpoint
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"
    headers = { 'X-CMC_PRO_API_KEY': CMC_API_KEY, 'Accept': 'application/json' }
    
    updates = {}
    batch_size = 50
    
    # Eksik olanları işle
    for i in range(0, len(missing_in_db), batch_size):
        batch_keys = missing_in_db[i:i+batch_size]
        
        # CMC'ye sorarken "-USD" kısmını siliyoruz (TAIKO-USD -> TAIKO)
        clean_symbols_map = {k: k.replace("-USD", "") for k in batch_keys}
        clean_symbols_list = list(clean_symbols_map.values())
        
        params = {'symbol': ','.join(clean_symbols_list)}
        
        try:
            r = requests.get(url, headers=headers, params=params)
            data = r.json().get('data', {})
            
            for clean_sym, details in data.items():
                # Orijinal anahtarı (TAIKO-USD) bul
                original_key = next((k for k, v in clean_symbols_map.items() if v == clean_sym), None)
                
                if original_key and details.get('logo'):
                    logo_raw = details.get('logo')
                    name = details.get('name')
                    
                    # Logoyu indir ve Firebase Storage'a yükle
                    final_url = upload_logo(logo_raw, clean_sym, "crypto")
                    
                    # Güncelleme listesine ekle
                    updates[original_key] = {"name": name, "logo": final_url}
                    print(f"      📥 {original_key} ({name}) logosu hazırlandı.")
            
        except Exception as e:
            print(f"   ⚠️ CMC API Hatası: {e}")
            
    # Sadece yeni bulunanları MEVCUT verinin üzerine ekle (Merge)
    if updates:
        crypto_ref.set(updates, merge=True)
        print(f"   💾 {len(updates)} adet yeni logo system_data/kripto dosyasına eklendi.")
    else:
        print("   ℹ️ Eklenecek yeni logo bulunamadı.")

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- ÖZEL MANUEL LOGO YÜKLEYİCİ ---")
    
    # Sadece kripto fonksiyonunu çalıştırıyoruz.
    sync_manual_crypto_logos()
    
    print("\n🎉 İŞLEM TAMAMLANDI!")
