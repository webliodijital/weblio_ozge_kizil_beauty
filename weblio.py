import os
import re
import io
from google import genai
from google.genai import types
from PIL import Image, ImageOps, ImageDraw

# --- 1. AYARLAR ---
GEMINI_API_KEY = "AIzaSyDsPeVLNgYJszQBuZBLyyAOgPxqRvfs8SA"
MODEL_NAME = 'imagen-4.0-generate-001' 
HTML_FILE = "index.html"
LOGO_PATH = "assets/logo.png"

# --- 2. GÜVENLİ VERİ ÇEKİCİ ---
def get_clean_data():
    if not os.path.exists(HTML_FILE):
        print(f"❌ {HTML_FILE} bulunamadı!")
        return None
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    def fetch_val(key):
        match = re.search(fr'{key}:\s*"(.*?)"', content)
        return match.group(1) if match else ""

    data = {
        "businessName": fetch_val("businessName"),
        "primaryColor": fetch_val("primary"),
        "slogan": fetch_val("slogan"),
        "tagline": fetch_val("tagline"),
        "description": fetch_val("description"),
        "tasks": []
    }
    
    # Standart Resimler & Gallery
    all_assets = re.findall(r'assets/(?:hero_bg|hero_mobil|about_mila|service_[\w\-_]+|galeri_[\w\-_]+)\.(?:webp|png|jpg)', content)
    for asset in set(all_assets):
        data["tasks"].append({"path": asset, "type": "standard"})

    # Instagram GIF'leri (Özel İstek)
    insta_assets = re.findall(r'assets/instagram_\d+\.gif', content)
    for asset in set(insta_assets):
        data["tasks"].append({"path": asset, "type": "insta_gif"})

    # Before/After
    trans_pattern = re.compile(r'{\s*title:\s*"(.*?)",.*?before:\s*"(.*?)",\s*after:\s*"(.*?)"', re.DOTALL)
    for title, before_path, after_path in trans_pattern.findall(content):
        data["tasks"].append({"path": before_path, "type": "before", "context": title})
        data["tasks"].append({"path": after_path, "type": "after", "context": title})

    return data

# --- 3. CINEMATIC GIF MOTORU (Zoom Efekti) ---
def create_cinematic_gif(base_img, target_path, logo_img=None):
    print(f"🎬 Sinematik efekt uygulanıyor: {target_path}")
    frames = []
    width, height = base_img.size
    
    # 4 Saniyelik döngü (20 kare, her kare 200ms)
    steps = 20 
    for i in range(steps):
        # Yavaşça zoom yap (%110'a kadar)
        zoom_factor = 1 + (i * 0.005) 
        new_w, new_h = int(width * zoom_factor), int(height * zoom_factor)
        
        frame = base_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Merkeze göre kırp (Zoom hissi için)
        left = (new_w - width) / 2
        top = (new_h - height) / 2
        right = (new_w + width) / 2
        bottom = (new_h + height) / 2
        frame = frame.crop((left, top, right, bottom))
        
        # Logoyu her kareye mühürle
        if logo_img:
            lw = int(width * 0.22)
            lp = (lw / float(logo_img.size[0]))
            lh = int((float(logo_img.size[1]) * float(lp)))
            l_res = logo_img.resize((lw, lh), Image.Resampling.LANCZOS)
            frame.paste(l_res, (width - lw - 30, height - lh - 30), l_res)
            
        frames.append(frame.convert("P", palette=Image.ADAPTIVE))

    # GIF olarak kaydet
    frames[0].save(
        target_path,
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0,
        optimize=True
    )

# --- 4. LOGO & RESİM İŞLEME ---
def handle_logos(client, business_name, primary_color):
    if os.path.exists(LOGO_PATH):
        return Image.open(LOGO_PATH).convert("RGBA")
    print(f"✨ Logo tasarlanıyor...")
    logo_prompt = f"Minimalist luxury vector logo for '{business_name}', {primary_color} color, white background."
    try:
        response = client.models.generate_images(model=MODEL_NAME, prompt=logo_prompt, config=types.GenerateImagesConfig(number_of_images=1))
        raw_bytes = response.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 235 and item[1] > 235 and item[2] > 235: newData.append((255, 255, 255, 0))
            else: newData.append(item)
        img.putdata(newData)
        img.save(LOGO_PATH)
        return img
    except: return None

def process_and_save_webp(pil_img, target_path, logo_img=None):
    final_path = target_path.rsplit('.', 1)[0] + ".webp"
    img = pil_img.convert("RGBA")
    if logo_img:
        base_w, base_h = img.size
        logo_w = int(base_w * 0.22) 
        w_percent = (logo_w / float(logo_img.size[0]))
        logo_h = int((float(logo_img.size[1]) * float(w_percent)))
        logo_resized = logo_img.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        img.paste(logo_resized, (base_w - logo_w - 30, base_h - logo_h - 30), logo_resized)
    img.convert("RGB").save(final_path, "WEBP", quality=82)
    print(f"✅ Kaydedildi: {final_path}")

# --- 5. ANA MOTOR ---
def start_engine():
    data = get_clean_data()
    if not data: return

    if not os.path.exists('assets'): os.makedirs('assets')
    client = genai.Client(api_key=GEMINI_API_KEY)
    logo_img = handle_logos(client, data['businessName'], data['primaryColor'])
    theme = f"Luxury {data['primaryColor']} aesthetic, realistic, medical beauty clinic lighting, 8k."

    print(f"🚀 Weblio Art Pro Engine Başladı...")

    for task in data['tasks']:
        img_path = task['path']
        # Resim/GIF zaten varsa atla
        if os.path.exists(img_path) or os.path.exists(img_path.replace(".png", ".webp")):
            continue

        target_name = img_path.split('/')[-1].lower()
        base_prompt = ""

        # --- ZEKİ PROMPT ATAMALARI ---
        if task['type'] == "insta_gif":
            # Instagram GIF'leri için daha lifestyle ve hareketli promptlar
            prompts = [
                "Elegant woman receiving a luxury facial massage, steam in background, cinematic",
                "Aesthetic clinic interior with blooming flowers and rose gold details, soft camera movement feel",
                "Close up of professional aesthetician hands preparing premium skincare products",
                "Fit woman smiling after a body contouring treatment in a luxury room",
                "Modern beauty clinic hallway with minimalist art and soft lighting"
            ]
            idx = int(re.search(r'\d+', target_name).group()) - 1
            base_prompt = prompts[idx % len(prompts)]
        elif task['type'] == "before":
            base_prompt = f"Natural untreated face showing {task['context'].lower()}, real skin texture, before procedure"
        elif task['type'] == "after":
            base_prompt = f"Perfect glowing results after {task['context'].lower()} treatment, clinical excellence"
        elif "hero_bg" in target_name: base_prompt = f"Wide lens view of {data['businessName']} luxury clinic interior"
        elif "hero_mobil" in target_name: base_prompt = "Portrait of an elegant woman with perfect skin, soft focus"
        elif "service_lazer" in target_name: base_prompt = "Macro photography of laser hair removal on silk skin"
        elif "service_cilt" in target_name: base_prompt = "Hydrafacial medical skincare treatment, radiant glow"
        else: base_prompt = "Luxury aesthetic beauty detail photography"

        print(f"🎨 Üretiliyor: {target_name}")
        try:
            response = client.models.generate_images(model=MODEL_NAME, prompt=f"{base_prompt}. {theme}", config=types.GenerateImagesConfig(number_of_images=1))
            raw_data = response.generated_images[0].image.image_bytes
            pil_img = Image.open(io.BytesIO(raw_data))

            if task['type'] == "insta_gif":
                create_cinematic_gif(pil_img, img_path, logo_img)
            else:
                process_and_save_webp(pil_img, img_path, logo_img)
        except Exception as e:
            print(f"❌ {target_name} hatası: {e}")

if __name__ == "__main__":
    start_engine()
    print("\n✨ Weblio Tüm Görselleri ve Sinematik GIF'leri Hazırladı!")