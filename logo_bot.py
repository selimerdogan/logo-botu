import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

# --- AYARLAR ---
# Bu bot ayda 1 çalışacağı için veritabanını yormaz.
# Logoları 'metadata' koleksiyonuna kaydedeceğiz.

# --- FIREBASE BAĞLANTISI ---
if not os.path.exists("serviceAccountKey.json"):
    print("HATA: serviceAccountKey.json bulunamadı!")
    sys.exit(1)

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"HATA: Firebase hatası: {e}")
    sys.exit(1)

# ==============================================================================
# 1. VARLIK LİSTELERİ (ANA BOTTAN KOPYALANDI - SENKRON OLMASI İÇİN)
# ==============================================================================
# Ana koddaki listelerin AYNISI olmalı ki isimler tutsun.

LISTE_ABD = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "LLY", "AVGO", "V", "JPM", "XOM", "WMT", "UNH", "MA", "PG", "JNJ", "HD", "MRK", "COST", "ABBV", "CVX", "CRM", "BAC", "AMD", "PEP", "KO", "NFLX", "ADBE", "DIS", "MCD", "CSCO", "TMUS", "ABT", "INTC", "INTU", "CMCSA", "PFE", "NKE", "WFC", "QCOM", "TXN", "DHR", "PM", "UNP", "IBM", "AMGN", "GE", "HON", "BA", "SPY", "QQQ", "UBER", "PLTR",
    "LIN", "ACN", "RTX", "VZ", "T", "CAT", "LOW", "BKNG", "NEE", "GS", "MS", "BMY", "DE", "MDT", "SCHW", "BLK", "TJX", "PGR", "COP", "ISRG", "LMT", "ADP", "AXP", "MMC", "GILD", "VRTX", "C", "MDLZ", "ADI", "REGN", "LRCX", "CI", "CVS", "BSX", "ZTS", "AMT", "ETN", "SLB", "FI", "BDX", "SYK", "CB", "EOG", "TM", "SO", "CME", "MU", "KLAC", "PANW", "MO", "SHW", "SNPS", "EQIX", "CDNS", "ITW", "DUK", "CL", "APH", "PYPL", "CSX", "PH", "TGT", "USB", "ICE", "NOC", "WM", "FCX", "GD", "NXPI", "ORLY", "HCA", "MCK", "EMR", "MAR", "PNC", "PSX", "BDX", "ROP", "NSC", "GM", "FDX", "MCO", "AFL", "CARR", "ECL", "APD", "AJG", "MSI", "AZO", "TT", "WMB", "TFC", "COF", "PCAR", "D", "SRE", "AEP", "HLT", "O", "TRV", "MET", "PSA", "PAYX", "ROST", "KMB", "JCI", "URI", "ALL", "PEG", "ED", "XEL", "GWW", "YUM", "FAST", "WELL", "AMP", "DLR", "VLO", "AME", "CMI", "FIS", "ILMN", "AIG", "KR", "PPG", "KMI", "EXC", "LUV", "DAL"
]

LISTE_KRIPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "DOGE-USD",
    "TRX-USD", "DOT-USD", "LINK-USD", "LTC-USD", "SHIB-USD", "ATOM-USD",
    "XLM-USD", "NEAR-USD", "INJ-USD", "FIL-USD", "HBAR-USD", "LDO-USD", "ARB-USD",
    "ALGO-USD", "SAND-USD", "QNT-USD", "VET-USD", "OP-USD", "EGLD-USD", "AAVE-USD",
    "THETA-USD", "AXS-USD", "MANA-USD", "EOS-USD", "FLOW-USD", "XTZ-USD",
    "MKR-USD", "SNX-USD", "NEO-USD", "JASMY-USD", "KLAY-USD", "GALA-USD", "CFX-USD",
    "CHZ-USD", "CRV-USD", "ZEC-USD", "XEC-USD", "IOTA-USD",
    "LUNC-USD", "BTT-USD", "MINA-USD", "DASH-USD", "CAKE-USD", "RUNE-USD", "KAVA-USD",
    "ENJ-USD", "ZIL-USD", "BAT-USD", "TWT-USD", "QTUM-USD", "CELO-USD", "RVN-USD",
    "LRC-USD", "ENS-USD", "CVX-USD", "YFI-USD", "ANKR-USD", "1INCH-USD", "HOT-USD"
]

LISTE_DOVIZ = [
    "USDTRY=X", "EURTRY=X", "GBPTRY=X", "CHFTRY=X", "CADTRY=X", "JPYTRY=X", "AUDTRY=X",
    "EURUSD=X", "GBPUSD=X"
]

# BIST listesini uzun olduğu için buraya tekrar yapıştırmıyorum ama
# normalde 'tumveriyi_cek.py' içindeki o uzun LISTE_BIST buraya da lazım.
# Şimdilik örnek 5 tane koyuyorum, sen ana dosyadaki uzun listeyi buraya kopyala.
LISTE_BIST = [
    "THYAO.IS", "GARAN.IS", "SISE.IS", "EREGL.IS", "ASELS.IS" # ... ve diğerleri
]

# ==============================================================================
# LOGO OLUŞTURUCU MOTOR
# ==============================================================================

logo_map = {
    "borsa_tr_tl": {},
    "borsa_abd_usd": {},
    "kripto_usd": {},
    "doviz_tl": {},
    "altin_tl": {}
}

print("--- LOGO BOTU BAŞLADI ---")

# 1. KRİPTO LOGOLARI (CoinCap API - Çok Kaliteli)
# ----------------------------------------------------
print("1. Kripto Logoları hazırlanıyor...")
for coin in LISTE_KRIPTO:
    symbol = coin.split("-")[0].lower() # BTC-USD -> btc
    # CoinCap ücretsiz ikon servisi
    url = f"https://assets.coincap.io/assets/icons/{symbol}@2x.png"
    logo_map["kripto_usd"][symbol.upper()] = url

# 2. DÖVİZ BAYRAKLARI (FlagCDN)
# ----------------------------------------------------
print("2. Döviz Bayrakları hazırlanıyor...")
# Manuel Eşleştirme (Para birimi -> Ülke Kodu)
ulke_kodlari = {
    "USD": "us", "EUR": "eu", "GBP": "gb", "CHF": "ch", 
    "CAD": "ca", "JPY": "jp", "AUD": "au", "CNY": "cn",
    "DX-Y": "us" # Dolar endeksi
}

for kur in LISTE_DOVIZ:
    # Sembolü temizle (USDTRY=X -> USD)
    ana_para = kur.replace("TRY=X", "").replace("=X", "").replace("USD", "").replace("-", "")
    
    # Özel durumlar (EURUSD gibi pariteler için ilkini al)
    if len(ana_para) > 3: ana_para = ana_para[:3]
    if kur == "EURUSD=X": ana_para = "EUR"
    if kur == "GBPUSD=X": ana_para = "GBP"
    if kur == "DX-Y.NYB": ana_para = "USD"
    if "USD" in kur and "TRY" in kur: ana_para = "USD"

    # Bayrak Linki
    kod = ulke_kodlari.get(ana_para, "un") # un = unknown
    url = f"https://flagcdn.com/w320/{kod}.png"
    
    # Veritabanı anahtarı (tumveriyi_cek.py ile aynı olmalı)
    db_key = kur.replace("TRY=X", "").replace("=X", "")
    logo_map["doviz_tl"][db_key] = url

# 3. BIST & ABD HİSSELERİ (UI Avatars - Harfli Logo)
# ----------------------------------------------------
print("3. Hisse Logoları (Avatar) hazırlanıyor...")
# Gerçek logo bulmak zor ve paralı olduğu için "Harfli Avatar" en temiz yöntemdir.
# Örnek: Apple -> Gri zemin üzerinde "AA" yazan şık ikon.

def get_avatar_url(sembol):
    # .IS uzantısını at
    temiz = sembol.replace(".IS", "")
    # Rastgele renkli ve şık bir avatar linki oluştur
    return f"https://ui-avatars.com/api/?name={temiz}&background=0D8ABC&color=fff&size=128&bold=true"

for hisse in LISTE_ABD:
    logo_map["borsa_abd_usd"][hisse] = get_avatar_url(hisse)

for hisse in LISTE_BIST:
    # BIST Hisseleri için isim temizliği
    ad = hisse.replace(".IS", "")
    # BIST için Kırmızı-Beyaz tonu yapalım
    url = f"https://ui-avatars.com/api/?name={ad}&background=TK&color=fff&size=128&bold=true" 
    # Not: Background'a renk kodu verebilirsin (Örn: b30000 = Kırmızı)
    url = f"https://ui-avatars.com/api/?name={ad}&background=b30000&color=fff&size=128&bold=true"
    logo_map["borsa_tr_tl"][ad] = url

# 4. ALTIN (Sabit Altın İkonu)
# ----------------------------------------------------
print("4. Altın İkonları atanıyor...")
# İnternetten bulduğumuz güzel bir altın ikonu (PNG)
GOLD_ICON = "https://cdn-icons-png.flaticon.com/512/1975/1975709.png" # Altın Külçe
SILVER_ICON = "https://cdn-icons-png.flaticon.com/512/2622/2622256.png" # Gümüş

# Altın türlerini manuel tahmin ediyoruz (Listemiz belli değil, dinamik çekiyorduk)
# Ama genel bir map yapabiliriz.
altin_turleri = [
    "Gram Altın", "Çeyrek Altın", "Yarım Altın", "Tam Altın", 
    "Cumhuriyet A.", "Ata Altın", "14 Ayar Altın", "18 Ayar Altın", 
    "22 Ayar Bilezik", "Beşli Altın", "Gremse Altın", "Reşat Altın", 
    "Hamit Altın", "Has Altın"
]

for altin in altin_turleri:
    logo_map["altin_tl"][altin] = GOLD_ICON

# Gümüş varsa özel ikon
logo_map["altin_tl"]["Gümüş"] = SILVER_ICON


# ==============================================================================
# KAYIT (METADATA)
# ==============================================================================
print("Veritabanına kaydediliyor...")

# 'system' koleksiyonunda 'app_data' dokümanına yazıyoruz.
# Uygulama açılışta burayı bir kere okuyacak.
doc_ref = db.collection(u'system').document(u'assets_metadata')
doc_ref.set({u'logos': logo_map}, merge=True)

print("✅ LOGO İŞLEMİ TAMAMLANDI.")
print(f"Toplam: {len(logo_map['borsa_tr_tl'])} BIST, {len(logo_map['kripto_usd'])} Kripto logosu işlendi.")
