import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import sys
import os
import json
import time

# --- AYARLAR ---
headers_general = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# --- KİMLİK KONTROLLERİ ---
firebase_key_str = os.environ.get('FIREBASE_KEY')
CMC_API_KEY = os.environ.get('CMC_API_KEY')

if firebase_key_str:
    cred = credentials.Certificate(json.loads(firebase_key_str))
elif os.path.exists("serviceAccountKey.json"):
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    print("HATA: Firebase anahtarı bulunamadı!")
    sys.exit(1)

try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"HATA: Firebase hatası: {e}")
    sys.exit(1)

# ==============================================================================
# SADECE ÖZEL LİSTE KRİPTO (CMC QUOTES API)
# ==============================================================================
def get_crypto_special_list():
    if not CMC_API_KEY:
        print("    -> ⚠️ CMC Key Yok.")
        return {}

    # --- SENİN ÖZEL LİSTEN ---
    # Not: CoinMarketCap sembolleri birebir eşleşmelidir.
    MANUAL_COINS = [
        "ELG", "LSK", "SKR", "RESOLV", "UB", "TAIKO", "GWEI", "EUL", 
        "KLK", "FB", "LISUSD", "ICNT", "GOHOME", "GOOGLON", "UCN", 
        "BUSD", "VBUSD", "BLAST", "ORE", "HUMA", "SHX", "LBT", 
        "SPELL", "USDON"
    ]
    
    print(f"🚀 Özel Kripto Listesi ({len(MANUAL_COINS)} adet) çekiliyor...")
    
    # Quotes Endpoint: Belirli sembollerin fiyatını çeker
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    
    # Sembolleri virgülle birleştir (ELG,LSK,SKR...)
    symbols_str = ",".join(MANUAL_COINS)
    
    params = {
        'symbol': symbols_str,
        'convert': 'USD'
    }
    headers = {
        'Accepts': 'application/json', 
        'X-CMC_PRO_API_KEY': CMC_API_KEY
    }
    
    data = {}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        response_json = r.json()
        
        # Hata kontrolü (Örn: Listede geçersiz bir coin varsa)
        if r.status_code != 200:
            print(f"    -> API Mesajı: {response_json.get('status', {}).get('error_message')}")
        
        items = response_json.get('data', {})
        
        for sym, item_data in items.items():
            # Bazen aynı sembolden birden fazla olabilir (Liste döner), biz ilkini alırız veya obje döner.
            # CMC Quotes endpoint genelde obje döner: "BTC": { ... }
            # Ancak duplicate sembol varsa liste dönebilir. Basitlik için obje varsayıyoruz.
            
            coin = item_data
            if isinstance(item_data, list):
                coin = item_data[0] # İlk eşleşeni al
                
            quote = coin['quote']['USD']
            symbol = coin['symbol']
            
            # Veritabanı anahtarı: TAIKO-USD
            db_key = f"{symbol}-USD"
            
            data[db_key] = {
                "price": round(float(quote['price']), 6), # Düşük fiyatlı coinler için hassasiyet arttı
                "change": round(float(quote['percent_change_24h']), 2),
                "name": coin['name'],
                "type": "crypto"
            }
            
    except Exception as e: 
        print(f"    -> ⚠️ Kripto Hatası: {e}")
        
    return data

# ==============================================================================
# KAYIT VE ÇALIŞTIRICI
# ==============================================================================
try:
    print("--- ÖZEL MARKET BOTU BAŞLIYOR ---")
    
    # Sadece kripto verisi çekiyoruz
    kripto_verisi = get_crypto_special_list()
    
    if kripto_verisi:
        final_paket = {
            "kripto_usd": kripto_verisi,
            # Diğer alanları boşaltıyoruz ki eski veriler kafa karıştırmasın (İstersen silebilirsin)
            "borsa_abd_usd": {},
            "borsa_tr_tl": {},
            "altin_tl": {},
            "doviz_tl": {},
            "fon_tl": {},
            "endeks_tr": {},
            "last_updated": firestore.SERVER_TIMESTAMP
        }

        # Firebase'e Yaz
        db.collection(u'market_data').document(u'LIVE_PRICES').set(final_paket)
        
        print(f"✅ [{len(kripto_verisi)} adet] Coin fiyatı güncellendi.")
        print("❌ Diğer tüm piyasa verileri (BIST, ABD, Altın vs.) temizlendi.")
    else:
        print("❌ HATA: Veri çekilemedi veya API limitine takıldı.")
        sys.exit(1)

except Exception as e:
    print(f"KRİTİK HATA: {e}")
    sys.exit(1)
