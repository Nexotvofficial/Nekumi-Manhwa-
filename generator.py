import os
import json
import re
import shutil
from datetime import datetime
from PIL import Image

# Configuración principal
BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"
BASE_URL = "https://raw.githubusercontent.com/Nexotvofficial/Nekumi-Manhwa-/main/catalog"
IMG_BASE_URL = "https://raw.githubusercontent.com/Nexotvofficial/Nekumi-Manhwa-/main/img"

# Elementos del sistema a ignorar en la raíz
SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "img", "generator.py", "mangas.json", 
    "README.md", "app", "build", ".gitignore"
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

def create_webp(input_path, output_path, quality=80):
    """Convierte y optimiza imágenes a WebP"""
    try:
        with Image.open(input_path) as img:
            img.convert("RGB").save(output_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"❌ Error procesando {input_path}: {e}")
        return False

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
    Busca únicamente la portada en la carpeta img/ asociada al ID del manhwa.
    """
    for ext in ['.webp', '.png', '.jpg', '.jpeg']:
        img_file = os.path.join(IMG_DIR, f"{manga_id}{ext}")
        if os.path.exists(img_file):
            # Si la subiste en png/jpg, la optimiza a webp automáticamente
            if not ext.endswith('.webp'):
                target_img_path = os.path.join(IMG_DIR, f"{manga_id}.webp")
                if create_webp(img_file, target_img_path):
                    if os.path.exists(img_file) and img_file != target_img_path:
                        os.remove(img_file)
            return f"{IMG_BASE_URL}/{manga_id}.webp"

    return ""

def generate_catalog():
    print("🚀 Iniciando generación automática de catálogo...")
    
    auto_fix_and_organize()

    manga_list = []

    for manga_folder in sorted(os.listdir(BASE_DIR)):
        manga_path = os.path.join(BASE_DIR, manga_folder)
        if not os.path.isdir(manga_path):
            continue

        manga_id = manga_folder.lower().replace(" ", "-")
        default_title = manga_folder.replace("-", " ").title()
        
        meta = load_manga_metadata(manga_path, default_title)
        chapters = []

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

                if not img_name.lower().endswith('.webp'):
                    if create_webp(img_path, target_webp_path):
                        if os.path.exists(img_path) and img_path != target_webp_path:
                            os.remove(img_path)
                else:
                    if img_name != target_webp_name:
                        shutil.move(img_path, target_webp_path)

                page_url = f"{BASE_URL}/{manga_folder}/{chap_folder}/{target_webp_name}"
                pages.append(page_url)

            if pages:
                chapters.append({
                    "id": chap_id,
                    "number": chap_num,
                    "title": f"Capítulo {chap_num}",
                    "pages_count": len(pages),
                    "pages": pages
                })

        chapters.sort(key=lambda x: x["number"])

        if chapters:
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

    print(f"\n✅ Catálogo generado con éxito en '{OUTPUT_JSON}'")
    print(f"📊 Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
