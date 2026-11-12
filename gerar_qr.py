import urllib.request
import urllib.parse
import sys
import os

def generate_qr(target_url, filename="qrcode_slides.png"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(base_dir, filename)
    encoded_url = urllib.parse.quote(target_url.strip())
    api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=1000x1000&margin=20&data={encoded_url}"
    
    print(f"Gerando QR Code para: {target_url}...")
    urllib.request.urlretrieve(api_url, out_path)
    print(f"✅ QR Code gerado com sucesso em alta resolucao!")
    print(f"Arquivo: {out_path}")
    return out_path

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input("Digite a sua URL do Render (ex: https://quiz-custodia.onrender.com): ")
    if target:
        if not target.startswith("http"):
            target = "https://" + target
        generate_qr(target)
