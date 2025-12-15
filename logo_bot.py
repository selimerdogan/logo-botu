import requests
import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import sys
import json
import io
from PIL import Image  # Resim işleme için gerekli (pip install Pillow)
from datetime import datetime

# --- AYARLAR ---
headers_general = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
}

# --- KİMLİK KONTROLLERİ VE BAŞLATMA ---
firebase_key_str = os.environ.get('FIREBASE_KEY')
CMC_API_KEY = os.environ.get('CMC_API_KEY')

# Firebase Storage Bucket Adı (Senin linkinden aldım)
BUCKET_NAME = "vario-264d9.firebasestorage.app"

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
        # Storage Bucket ayarını buraya ekledik
        firebase_admin.initialize_app(cred, {
            'storageBucket': BUCKET_NAME
        })
    db = firestore.client()
    bucket = storage.bucket() # Storage erişimi
except Exception as e:
    print(f"HATA: Firebase hatası: {e}")
    sys.exit(1)

# ==============================================================================
# YARDIMCI FONKSİYON: RESMİ İNDİR, KÜÇÜLT, YÜKLE
# ==============================================================================
def upload_logo(original_url, file_name, folder_name):
    """
    Verilen URL'deki resmi indirir, 128x128 PNG yapar ve Firebase Storage'a yükler.
    Geriye Firebase'deki kalıcı public linki döner.
    """
    # 1. Eğer link zaten bizim Firebase'e aitse, işlem yapma, aynen döndür.
    if "firebasestorage.googleapis.com" in original_url:
        return original_url

    # 2. Eğer logo yoksa veya avatar servisi ise (Tasarruf için avatarı yüklemiyoruz, direkt kullanıyoruz)
    if "ui-avatars.com" in original_url or not original_url:
        return original_url

    try:
        # 3. Resmi İndir
        resp = requests.get(original_url, headers=headers_general, timeout=10)
        if resp.status_code != 200:
            return original_url # İndirilemezse eskisini kullan

        # 4. Resmi İşle (Pillow ile)
        img_bytes = io.BytesIO(resp.content)
        img = Image.open(img_bytes)
        
        # PNG'ye çevir ve RGBA (Şeffaflık) koru
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
            
        # Boyutlandır (Standart 128x128px)
        img = img.resize((128, 128), Image.Resampling.LANCZOS)

        # Çıktı için hazırla
        output_io = io.BytesIO()
        img.save(output_io, format='PNG', optimize=True)
        image_data = output_io.getvalue()

        # 5. Firebase Storage'a Yükle
        # Dosya yolu: logos/kripto/BTC.png gibi olacak
        blob_path = f"logos/{folder_name}/{file_name}.png"
        blob = bucket.blob(blob_path)
        
        blob.upload_from_string(image_data, content_type="image/png")
        blob.make_public() # Dosyayı herkese açık yap

        # Yeni Linki Döndür
        return blob.public_url

    except Exception as e:
        print(f"   ⚠️ Hata ({file_name}): {e}")
        return original_url # Hata olursa orijinal linki kullanmaya devam et

# ==============================================================================
# 1. BIST & ABD (GÜNCELLENMİŞ - UPLOAD EKLENDİ)
# ==============================================================================
def get_tradingview_metadata(market):
    print(f"   -> {market.upper()} Logoları aranıyor ve yükleniyor...")
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
            count = 0
            
            print(f"      Toplam {len(items)} hisse işlenecek. Bu işlem biraz sürebilir...")

            for h in items:
                d = h.get('d', [])
                if len(d) > 2:
                    sembol = d[0] # Örn: THYAO
                    isim = d[1]   
                    logo_id = d[2]
                    
                    if logo_id:
                        raw_url = f"{base_logo_url}{logo_id}.svg"
                        # BURADA UPLOAD FONKSİYONUNU ÇAĞIRIYORUZ
                        # SVG'leri de indirip PNG'ye çevirecek.
                        final_logo = upload_logo(raw_url, sembol, f"stocks_{market}")
                    else:
                        final_logo = f"https://ui-avatars.com/api/?name={sembol}&background={bg_color}&color=fff&size=128&bold=true"
                    
                    if "," in isim: isim = isim.split(",")[0]
                    
                    data[sembol] = {"name": isim, "logo": final_logo}
                    
                    # İlerleme Çubuğu (Log kirliliği olmasın diye her 50 tanede bir yazdır)
                    count += 1
                    if count % 50 == 0:
                        print(f"      Processing... {count}/{len(items)}")

            print(f"      ✅ {market.upper()}: {len(data)} adet logo güncellendi.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (GÜNCELLENMİŞ - UPLOAD EKLENDİ)
# ==============================================================================
def get_crypto_metadata():
    print("2. Kripto Logoları (CMC) çekiliyor ve yükleniyor...")
    
    if not CMC_API_KEY:
        print("   -> ⚠️ CMC Key Yok! Manuel liste.")
        # Manuel listedekileri de upload edelim
        btc_url = upload_logo("https://s2.coinmarketcap.com/static/img/coins/64x64/1.png", "BTC-USD", "crypto")
        eth_url = upload_logo("https://s2.coinmarketcap.com/static/img/coins/64x64/1027.png", "ETH-USD", "crypto")
        return {
            "BTC-USD": {"name": "Bitcoin", "logo": btc_url},
            "ETH-USD": {"name": "Ethereum", "logo": eth_url}
        }

    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
    params = {'start': '1', 'limit': '300', 'convert': 'USD'}
    headers = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}
    data = {}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 200:
            coins = r.json()['data']
            print(f"      {len(coins)} Kripto para işleniyor...")
            
            for coin in coins:
                sym = coin['symbol']
                name = coin['name']
                coin_id = coin['id']
                raw_logo = f"https://s2.coinmarketcap.com/static/img/coins/64x64/{coin_id}.png"
                
                # Piyasada kullanılan ID formatı
                key = f"{sym}-USD"
                
                # UPLOAD İŞLEMİ
                final_logo = upload_logo(raw_logo, key, "crypto")
                
                data[key] = {"name": name, "logo": final_logo}
                
            print(f"   -> ✅ CMC: {len(data)} adet kripto yüklendi.")
    except Exception as e:
        print(f"   -> ⚠️ CMC Hatası: {e}")
        
    return data

# ==============================================================================
# 3. FONLAR
# ==============================================================================
def get_fon_metadata():
    # Fonlar için şimdilik tek bir ikon kullanıyoruz, binlerce fonu tek tek yüklemeye gerek yok.
    # Senin belirlediğin "FON_ICON" zaten Firebase'de.
    print("3. Fon İsimleri (TEFAS) taranıyor...")
    data = {}
    
    # Senin verdiğin sabit ikon (zaten firebase linki)
    ICON_FUND = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/fon.png?alt=media&token=4fa44daa-d0e4-462e-8532-fc91b45f7bb1"
    
    url = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"
    headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.tefas.gov.tr"}
    
    try:
        simdi = datetime.now()
        tarih_str = simdi.strftime("%d.%m.%Y")
        payload = {"calismatipi": "2", "fontip": "YAT", "bastarih": tarih_str, "bittarih": tarih_str}
        
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            l = r.json().get('data', [])
            if len(l) > 0:
                for f in l:
                    kod = f['FONKODU']
                    isim = f['FONADI']
                    data[kod] = {"name": isim, "logo": ICON_FUND}
                print(f"   -> ✅ TEFAS: {len(data)} adet fon işlendi.")
    except Exception as e: 
        print(f"Hata: {e}")
    
    return data

# ==============================================================================
# 4. DÖVİZ & ALTIN (FlagCDN ve Sabit İkonlar)
# ==============================================================================
def get_doviz_altin_metadata():
    print("--- LOGO/METADATA HAZIRLANIYOR (Döviz & Altın) ---")
    
    # Senin verdiğin Firebase Linkleri (Zaten yüklenmiş)
    ICON_GOLD = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/altin.png?alt=media&token=5b6d72f7-b71d-4c3e-bd3f-203bfec892ed"
    ICON_METAL = "https://firebasestorage.googleapis.com/v0/b/vario-264d9.firebasestorage.app/o/gumus.png?alt=media&token=6ad7c54e-aebc-4879-bf4b-66d45e8a8233"

    # 1. DÖVİZ
    # Bayrakları indirmemize gerek yok, FlagCDN CDN olarak çok iyidir ve sabit kalır.
    doviz_config = {
        "USD": {"n": "ABD Doları", "c": "us"},
        "EUR": {"n": "Euro", "c": "eu"},
        "GBP": {"n": "İngiliz Sterlini", "c": "gb"},
        "CHF": {"n": "İsviçre Frangı", "c": "ch"},
        "JPY": {"n": "Japon Yeni", "c": "jp"},
        "RUB": {"n": "Rus Rublesi", "c": "ru"},
        "CNY": {"n": "Çin Yuanı", "c": "cn"},
        "BAE": {"n": "BAE Dirhemi", "c": "ae"},
        "CAD": {"n": "Kanada Doları", "c": "ca"}
    }

    data_doviz = {}
    for kod, info in doviz_config.items():
        data_doviz[kod] = {
            "name": info["n"], 
            "logo": f"https://flagcdn.com/w320/{info['c']}.png"
        }
            
    # 2. ALTIN
    altin_listesi = [
        "14 Ayar Bilezik", "18 Ayar Bilezik", "22 Ayar Bilezik", "Ata Altın",
        "Beşli Altın", "Cumhuriyet Altını", "Gram Altın", "Gram Gümüş",
        "Gram Has Altın", "Gram Paladyum", "Gram Platin", "Gremse Altın",
        "Hamit Altın", "Reşat Altın", "Tam Altın", "Yarım Altın",
        "Çeyrek Altın", "İkibuçuk Altın"
    ]
    
    data_altin = {}
    for isim in altin_listesi:
        if any(x in isim for x in ["Gümüş", "Platin", "Paladyum"]):
            ikon = ICON_METAL
        else:
            ikon = ICON_GOLD
        data_altin[isim] = {"name": isim, "logo": ikon}
    
    return data_doviz, data_altin

# ==============================================================================
# ANA ÇALIŞTIRMA BLOĞU
# ==============================================================================
if __name__ == "__main__":
    print("--- LOGO/METADATA MİGRASYON BAŞLIYOR (FIREBASE STORAGE) ---")
    print("NOT: Bu işlem ilk seferde biraz uzun sürebilir (Resimler indiriliyor...)")

    # 1. Verileri Çek ve Yükle
    meta_kripto = get_crypto_metadata()
    meta_bist = get_tradingview_metadata("turkey")
    # meta_abd = get_tradingview_metadata("america") # İstersen yorumu kaldır (Çok uzun sürer!)
    meta_fon = get_fon_metadata()
    meta_doviz, meta_altin = get_doviz_altin_metadata()

    # 2. Veritabanına Kaydet
    coll_ref = db.collection(u'system_data')

    if meta_bist: 
        coll_ref.document(u'bist').set({u'data': meta_bist})
        print("✅ BIST veritabanı güncellendi.")
        
    # if meta_abd: coll_ref.document(u'abd').set({u'data': meta_abd})
    
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
