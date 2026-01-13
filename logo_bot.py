import uuid # <-- En tepeye import uuid eklemeyi unutma!

def upload_logo(original_url, file_name, folder_name):
    """
    Resmi indirir, Firebase Storage'a yükler ve MOBİL UYUMLU (Token'lı) link döner.
    """
    # 1. Zaten bizim linkimizse veya FlagCDN ise elleme
    if "firebasestorage.googleapis.com" in original_url or "flagcdn.com" in original_url:
        return original_url
    
    if "ui-avatars.com" in original_url or not original_url:
        return original_url

    try:
        resp = requests.get(original_url, headers=headers_general, timeout=15)
        if resp.status_code != 200: return original_url 

        content_type = resp.headers.get('Content-Type', '')
        file_data = resp.content
        
        # Dosya Yolu
        if "svg" in content_type or original_url.endswith(".svg") or b"<svg" in file_data[:100]:
            extension = "svg"
            final_content_type = "image/svg+xml"
            blob_data = file_data # SVG direkt yüklenir
        else:
            # PNG Dönüştürme
            img_bytes = io.BytesIO(file_data)
            img = Image.open(img_bytes)
            if img.mode != 'RGBA': img = img.convert('RGBA')
            img = img.resize((128, 128), Image.Resampling.LANCZOS)
            
            output_io = io.BytesIO()
            img.save(output_io, format='PNG', optimize=True)
            blob_data = output_io.getvalue()
            extension = "png"
            final_content_type = "image/png"

        # --- KRİTİK DEĞİŞİKLİK BURADA ---
        blob_path = f"logos/{folder_name}/{file_name}.{extension}"
        blob = bucket.blob(blob_path)
        
        # 1. Token Oluştur
        new_token = str(uuid.uuid4())
        
        # 2. Metadata olarak token'ı ekle
        blob.metadata = {"firebaseStorageDownloadTokens": new_token}
        
        # 3. Yükle
        blob.upload_from_string(blob_data, content_type=final_content_type)
        
        # 4. İstemci (Client) için Download URL oluştur
        # Format: https://firebasestorage.googleapis.com/v0/b/[BUCKET]/o/[PATH]?alt=media&token=[TOKEN]
        encoded_path = blob_path.replace("/", "%2F") # URL için / işaretini kodla
        download_url = f"https://firebasestorage.googleapis.com/v0/b/{BUCKET_NAME}/o/{encoded_path}?alt=media&token={new_token}"

        return download_url

    except Exception as e:
        print(f"Hata ({file_name}): {e}")
        return original_url
