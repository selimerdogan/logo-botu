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
# 1. BIST & ABD (TRADINGVIEW SCANNER)
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
                    
                    logo_url = f"{base_logo_url}{logo_id}.svg" if logo_id else None
                    
                    # İsim temizliği
                    if "," in isim: isim = isim.split(",")[0]
                    
                    data[sembol] = {"name": isim, "logo": logo_url}
            
            print(f"      ✅ {len(data)} adet veri bulundu.")
    except Exception as e:
        print(f"      ⚠️ Hata: {e}")
    return data

# ==============================================================================
# 2. KRİPTO (CMC API - TOP 250)
