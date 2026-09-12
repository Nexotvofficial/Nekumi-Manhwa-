import os
import json
import re
import shutil
import urllib.parse
from datetime import datetime
from PIL import Image

# Configuración del Repositorio de GitHub
GITHUB_USER = "Nexotvofficial"
GITHUB_REPO = "Nekumi-Manhwa-"
BRANCH = "main"

# True para usar el CDN de jsDelivr (más rápido y sin límites de ancho de banda)
USE_JSDELIVR = True

BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"

SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "img", "generator.py", "mangas.json", 
    "uploaded_cache.json", "README.md", "app", "build", ".gitignore", ".workflows"
}

def get_media_url(file_path):
    clean_path = file_path.replace("\\", "/")
    clean_path = urllib.parse.quote(clean_path, safe='/')
    
    if USE_JSDELIVR:
        return f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{GITHUB_REPO}@{BRANCH}/{clean_path}"
    return f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{BRANCH}/{clean_path}"

def auto_fix_and_organize():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)
    if not os.path.exists(IMG_DIR):
        os.makedirs(IMG_DIR, exist_ok=True)

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

def create_webp(input_path, output_path, quality=80):
    try:
        pil_img = Image.open(input_path).convert("RGB")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pil_img.save(output_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"❌ Error procesando {input_path}: {e}")
        return False

def extract_chapter_number(folder_name):
    match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
    if match:
        num_str = match.group(1)
        return float(num_str) if '.' in num_str else int(num_str)
    return 1

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_manga_metadata(manga_path, default_title):
    metadata = {
        "title": default_title,
        "synopsis": "Sinopsis no disponible por el momento.",
        "status": "En emisión",
        "genres": ["Manhwa", "Acción"]
    }
    
    if not os.path.exists(manga_path):
        return metadata

    json_info = os.path.join(manga_path, "info.json")
    if os.path.exists(json_info):
        try:
            with open(json_info, "r", encoding="utf-8") as f:
                metadata.update(json.load(f))
        except Exception:
            pass
    return metadata

def generate_catalog():
    print("🚀 Procesando imágenes y generando URLs de GitHub/CDN...")
    auto_fix_and_organize()

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

    # 1. Optimización y conversión de portadas
    for manga_id in all_manga_ids:
        for ext in ['.webp', '.png', '.jpg', '.jpeg']:
            cover_src = os.path.join(IMG_DIR, f"{manga_id}{ext}")
            if os.path.exists(cover_src):
                target_cover = os.path.join(IMG_DIR, f"{manga_id}.webp")
                
                if cover_src != target_cover:
                    if cover_src.lower().endswith('.webp'):
                        shutil.move(cover_src, target_cover)
                    else:
                        if create_webp(cover_src, target_cover):
                            if os.path.exists(cover_src):
                                os.remove(cover_src)
                break

    # 2. Optimización segura de imágenes (Previene que se borren páginas)
    for manga_id in all_manga_ids:
        manga_path = os.path.join(BASE_DIR, manga_id)
        if os.path.exists(manga_path) and os.path.isdir(manga_path):
            for chap_folder in sorted(os.listdir(manga_path), key=natural_sort_key):
                chap_path = os.path.join(manga_path, chap_folder)
                if not os.path.isdir(chap_path):
                    continue

                raw_images = [
                    f for f in os.listdir(chap_path) 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover")
                ]
                images = sorted(raw_images, key=natural_sort_key)
                
                # PASO A: Renombrar a nombres temporales para evitar pisar archivos existentes
                safe_paths = []
                for index, img_name in enumerate(images):
                    img_path = os.path.join(chap_path, img_name)
                    temp_name = f"temp_page_{index:04d}.webp"
                    temp_path = os.path.join(chap_path, temp_name)

                    if img_name.lower().endswith('.webp'):
                        if os.path.abspath(img_path) != os.path.abspath(temp_path):
                            shutil.move(img_path, temp_path)
                        safe_paths.append(temp_path)
                    else:
                        if create_webp(img_path, temp_path):
                            if os.path.exists(img_path):
                                os.remove(img_path)
                            safe_paths.append(temp_path)
                        else:
                            # Si falla, mantenemos el archivo original con nombre seguro
                            _, ext = os.path.splitext(img_name)
                            fallback_path = os.path.join(chap_path, f"temp_page_{index:04d}{ext}")
                            shutil.move(img_path, fallback_path)
                            safe_paths.append(fallback_path)

                # PASO B: Renombrar de temporales al formato final secuencial
                for index, temp_path in enumerate(safe_paths):
                    _, ext = os.path.splitext(temp_path)
                    final_name = f"{index+1:03d}{ext}"
                    final_path = os.path.join(chap_path, final_name)
                    if os.path.abspath(temp_path) != os.path.abspath(final_path):
                        shutil.move(temp_path, final_path)

    # 3. Construcción del archivo mangas.json
    manga_list = []
    for manga_id in all_manga_ids:
        manga_path = os.path.join(BASE_DIR, manga_id)
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

                # Ahora lee TODOS los formatos de imagen, no solo webp
                raw_images = [
                    f for f in os.listdir(chap_path) 
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover")
                ]
                images = sorted(raw_images, key=natural_sort_key)

                pages = []
                for img_name in images:
                    target_img_path = os.path.join(chap_path, img_name)
                    if os.path.exists(target_img_path):
                        pages.append(get_media_url(target_img_path))

                if pages:
                    chapters.append({
                        "id": chap_id,
                        "number": chap_num,
                        "title": f"Capítulo {chap_num}",
                        "pages_count": len(pages),
                        "pages": pages
                    })

            chapters.sort(key=lambda x: x["number"])

        cover_path = os.path.join(IMG_DIR, f"{manga_id}.webp")
        cover_url = get_media_url(cover_path) if os.path.exists(cover_path) else ""

        manga_list.append({
            "id": manga_id,
            "title": meta["title"],
            "category": "manhwa",
            "cover": cover_url,
            "cover_thumb": cover_url,
            "status": meta.get("status", "En emisión"),
            "synopsis": meta.get("synopsis", "Sinopsis no disponible."),
            "genres": meta.get("genres", ["Manhwa"]),
            "total_chapters": len(chapters),
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "chapters": chapters
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Catálogo generado con éxito en '{OUTPUT_JSON}' usando enlaces de GitHub/jsDelivr.")

if __name__ == "__main__":
    generate_catalog()
