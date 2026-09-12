import os
import json
import re
import shutil
from datetime import datetime
from PIL import Image
import cv2
import numpy as np
import requests

# Configuración principal
BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"
IMGBB_API_KEY = "4b0b73663ee43670cab4cec476709bb4"

# Porcentaje de seguridad de recorte (ajustable)
TOP_CROP_PERCENT = 0.03    # 3% superior
BOTTOM_CROP_PERCENT = 0.04 # 4% inferior

# Elementos del sistema a ignorar en la raíz
SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "img", "generator.py", "mangas.json", 
    "README.md", "app", "build", ".gitignore", ".workflows"
}

def auto_fix_and_organize():
    """
    Anticipa y corrige errores de estructura de archivos/carpetas subidos por el usuario.
    """
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR, exist_ok=True)

    # 1. Corregir carpetas subidas por error en la raíz
    for item in os.listdir("."):
        if os.path.isdir(item) and item not in SYSTEM_ITEMS:
            target_path = os.path.join(BASE_DIR, item)
            print(f"🔧 [Auto-Fix] Moviendo carpeta desubicada '{item}' -> '{target_path}'")
            if os.path.exists(target_path):
                for sub_item in os.listdir(item):
                    s_path = os.path.join(item, sub_item)
                    t_path = os.path.join(target_path, sub_item)
                    if not os.path.exists(t_path):
                        shutil.move(s_path, t_path)
                shutil.rmtree(item)
            else:
                shutil.move(item, target_path)

    # 2. Corregir imágenes sueltas dentro de catalog/
    loose_images = [
        f for f in os.listdir(BASE_DIR) 
        if os.path.isfile(os.path.join(BASE_DIR, f)) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ]
    
    if loose_images:
        existing_mangas = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        target_manga = existing_mangas[0] if existing_mangas else "super-evolution"
        target_chap_dir = os.path.join(BASE_DIR, target_manga, "cap-1")
        
        os.makedirs(target_chap_dir, exist_ok=True)
        print(f"🔧 [Auto-Fix] Reubicando {len(loose_images)} imágenes sueltas a '{target_chap_dir}'")
        for img in loose_images:
            shutil.move(os.path.join(BASE_DIR, img), os.path.join(target_chap_dir, img))

def clean_watermark_cv2(image_path):
    """
    Usa OpenCV Inpainting para detectar textos/logos superpuestos en los bordes
    y eliminarlos reconstruyendo el fondo.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    h, w, _ = img.shape

    # 1. Recorte preventivo en bordes
    top_crop = int(h * TOP_CROP_PERCENT)
    bottom_crop = int(h * (1 - BOTTOM_CROP_PERCENT))
    img = img[top_crop:bottom_crop, 0:w]

    h, w, _ = img.shape

    # 2. Convertir a escala de grises
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Crear máscara para detectar texto/logos
    mask = np.zeros((h, w), dtype=np.uint8)
    margin = min(120, int(h * 0.12))

    top_region = gray[0:margin, :]
    bottom_region = gray[h-margin:h, :]

    _, top_thresh = cv2.threshold(top_region, 220, 255, cv2.THRESH_BINARY)
    _, bottom_thresh = cv2.threshold(bottom_region, 220, 255, cv2.THRESH_BINARY)

    mask[0:margin, :] = top_thresh
    mask[h-margin:h, :] = bottom_thresh

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)

    # 4. Aplicar Inpainting
    if np.sum(mask) > 0:
        cleaned_img = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    else:
        cleaned_img = img

    cleaned_rgb = cv2.cvtColor(cleaned_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cleaned_rgb)

def create_webp(input_path, output_path, quality=80, is_page=False):
    """Convierte, limpia marcas de agua y guarda la imagen final en WebP"""
    try:
        if is_page:
            pil_img = clean_watermark_cv2(input_path)
            if pil_img is None:
                pil_img = Image.open(input_path).convert("RGB")
        else:
            pil_img = Image.open(input_path).convert("RGB")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pil_img.save(output_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"❌ Error procesando {input_path}: {e}")
        return False

def upload_to_imgbb(image_path, name=None):
    """
    Sube una imagen local a la API de ImgBB y devuelve el enlace directo CDN.
    """
    url = "https://api.imgbb.com/1/upload"
    try:
        with open(image_path, "rb") as file:
            payload = {
                "key": IMGBB_API_KEY,
            }
            if name:
                payload["name"] = name
            
            files = {
                "image": file
            }
            
            response = requests.post(url, data=payload, files=files, timeout=30)
            data = response.json()
            
            if data.get("success"):
                direct_url = data["data"]["url"]
                return direct_url
            else:
                print(f"❌ Error de ImgBB API: {data.get('error', {}).get('message')}")
    except Exception as e:
        print(f"❌ Excepción al subir a ImgBB {image_path}: {e}")
    
    return None

def extract_chapter_number(folder_name):
    """Extrae el número de capítulo"""
    match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
    if match:
        num_str = match.group(1)
        return float(num_str) if '.' in num_str else int(num_str)
    return 1

def natural_sort_key(s):
    """Ordenamiento natural para archivos de capítulos"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_manga_metadata(manga_path, default_title):
    """Carga metadatos de info.json o info.txt si existen"""
    metadata = {
        "title": default_title,
        "synopsis": "Sinopsis no disponible por el momento.",
        "status": "En emisión",
        "genres": ["Manhwa", "Acción"]
    }
    
    if not os.path.exists(manga_path):
        return metadata

    json_info = os.path.join(manga_path, "info.json")
    txt_info = os.path.join(manga_path, "info.txt")

    if os.path.exists(json_info):
        try:
            with open(json_info, "r", encoding="utf-8") as f:
                data = json.load(f)
                metadata.update(data)
        except Exception:
            pass
    elif os.path.exists(txt_info):
        try:
            with open(txt_info, "r", encoding="utf-8") as f:
                metadata["synopsis"] = f.read().strip()
        except Exception:
            pass

    return metadata

def get_cover_from_img_dir(manga_id):
    """
    Procesa y sube únicamente la portada en la carpeta img/ a ImgBB.
    """
    if not os.path.exists(IMG_DIR):
        return ""

    for ext in ['.webp', '.png', '.jpg', '.jpeg']:
        img_file = os.path.join(IMG_DIR, f"{manga_id}{ext}")
        if os.path.exists(img_file):
            target_img_path = os.path.join(IMG_DIR, f"{manga_id}.webp")
            if img_file != target_img_path:
                if create_webp(img_file, target_img_path, is_page=False):
                    if os.path.exists(img_file):
                        os.remove(img_file)
            
            print(f"📤 Subiendo portada de '{manga_id}' a ImgBB...")
            uploaded_url = upload_to_imgbb(target_img_path, name=f"cover_{manga_id}")
            if uploaded_url:
                return uploaded_url

    return ""

def generate_catalog():
    print("🚀 Iniciando generación automática de catálogo con subida a ImgBB...")
    
    auto_fix_and_organize()

    manga_list = []
    
    catalog_mangas = set()
    if os.path.exists(BASE_DIR):
        for f in os.listdir(BASE_DIR):
            if os.path.isdir(os.path.join(BASE_DIR, f)):
                catalog_mangas.add(f.lower().replace(" ", "-"))

    img_mangas = set()
    if os.path.exists(IMG_DIR):
        for f in os.listdir(IMG_DIR):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                name_without_ext = os.path.splitext(f)[0]
                img_mangas.add(name_without_ext.lower().replace(" ", "-"))

    all_manga_ids = sorted(list(catalog_mangas.union(img_mangas)))

    for manga_id in all_manga_ids:
        manga_folder = manga_id
        manga_path = os.path.join(BASE_DIR, manga_folder)
        
        default_title = manga_id.replace("-", " ").title()
        meta = load_manga_metadata(manga_path, default_title)
        chapters = []

        if os.path.exists(manga_path) and os.path.isdir(manga_path):
            for chap_folder in sorted(os.listdir(manga_path), key=natural_sort_key):
                chap_path = os.path.join(manga_path, chap_folder)
                if not os.path.isdir(chap_path):
                    continue

                chap_id = chap_folder.lower().replace(" ", "-")
                chap_num = extract_chapter_number(chap_folder)
                
                raw_images = [
                    f for f in os.listdir(chap_path) 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover")
                ]
                images = sorted(raw_images, key=natural_sort_key)

                pages = []
                for index, img_name in enumerate(images):
                    img_path = os.path.join(chap_path, img_name)
                    target_webp_name = f"{index+1:03d}.webp"
                    target_webp_path = os.path.join(chap_path, target_webp_name)

                    if os.path.abspath(img_path) != os.path.abspath(target_webp_path):
                        if create_webp(img_path, target_webp_path, is_page=True):
                            if os.path.exists(img_path):
                                os.remove(img_path)
                    else:
                        temp_path = os.path.join(chap_path, f"temp_{target_webp_name}")
                        if create_webp(img_path, temp_path, is_page=True):
                            shutil.move(temp_path, target_webp_path)

                    print(f"📤 Subiendo {manga_id} / {chap_folder} / {target_webp_name} a ImgBB...")
                    imgbb_url = upload_to_imgbb(target_webp_path, name=f"{manga_id}_{chap_folder}_{index+1:03d}")
                    
                    if imgbb_url:
                        pages.append(imgbb_url)

                if pages:
                    chapters.append({
                        "id": chap_id,
                        "number": chap_num,
                        "title": f"Capítulo {chap_num}",
                        "pages_count": len(pages),
                        "pages": pages
                    })

            chapters.sort(key=lambda x: x["number"])

        cover_url = get_cover_from_img_dir(manga_id)

        manga_list.append({
            "id": manga_id,
            "title": meta["title"],
            "category": "manhwa",
            "cover": cover_url,
            "status": meta.get("status", "En emisión"),
            "synopsis": meta.get("synopsis", "Sinopsis no disponible."),
            "genres": meta.get("genres", ["Manhwa"]),
            "total_chapters": len(chapters),
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "chapters": chapters
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Catálogo generado con éxito en '{OUTPUT_JSON}' con enlaces ImgBB CDN")
    print(f"📊 Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
