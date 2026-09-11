import os
import json
import re
import shutil
from PIL import Image

# Configuración de carpetas y repositorio
BASE_DIR = "catalog"
OUTPUT_JSON = "mangas.json"
BASE_URL = "https://raw.githubusercontent.com/Nexotvofficial/Nekumi-Manhwa-/main/catalog"

# Carpetas y archivos del sistema a ignorar en la raíz
SYSTEM_ITEMS = {".github", ".git", "catalog", "generator.py", "mangas.json", "README.md", "app", "build"}

def auto_fix_root_folders():
    """
    Si una carpeta de manhwa se sube por error en la raíz (ej: /crazy-demon),
    el script la mueve automáticamente dentro de /catalog/
    """
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)

    root_items = os.listdir(".")
    for item in root_items:
        if os.path.isdir(item) and item not in SYSTEM_ITEMS:
            target_path = os.path.join(BASE_DIR, item)
            print(f" Corregida ubicación: Moviendo '{item}' a '{target_path}'...")
            if os.path.exists(target_path):
                # Si ya existe en catalog, mueve los capítulos internos
                for sub_item in os.listdir(item):
                    s_path = os.path.join(item, sub_item)
                    t_path = os.path.join(target_path, sub_item)
                    if not os.path.exists(t_path):
                        shutil.move(s_path, t_path)
                shutil.rmtree(item)
            else:
                shutil.move(item, target_path)

def create_webp(input_path, output_path, quality=80):
    """Convierte y optimiza imágenes a formato WebP"""
    try:
        with Image.open(input_path) as img:
            img.convert("RGB").save(output_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"Error procesando {input_path}: {e}")
        return False

def extract_chapter_number(folder_name):
    """Detecta el número del capítulo desde el nombre de la carpeta"""
    match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
    if match:
        num_str = match.group(1)
        return float(num_str) if '.' in num_str else int(num_str)
    return 1

def generate_catalog():
    # 1. Asegurar la estructura correcta automáticamente
    auto_fix_root_folders()

    manga_list = []

    # 2. Recorrer la carpeta catalog/
    for manga_folder in sorted(os.listdir(BASE_DIR)):
        manga_path = os.path.join(BASE_DIR, manga_folder)
        if not os.path.isdir(manga_path):
            continue

        manga_id = manga_folder.lower().replace(" ", "-")
        manga_title = manga_folder.replace("-", " ").title()
        
        chapters = []
        cover_url = ""

        # Recorrer los capítulos
        for chap_folder in sorted(os.listdir(manga_path)):
            chap_path = os.path.join(manga_path, chap_folder)
            if not os.path.isdir(chap_path):
                continue

            chap_id = chap_folder.lower().replace(" ", "-")
            chap_num = extract_chapter_number(chap_folder)
            
            raw_images = [f for f in os.listdir(chap_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            images = sorted(raw_images, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])

            pages = []
            for index, img_name in enumerate(images):
                img_path = os.path.join(chap_path, img_name)
                webp_name = f"{index+1:03d}.webp"
                webp_path = os.path.join(chap_path, webp_name)

                # Convertir a WebP y reemplazar original si no lo es
                if not img_name.endswith('.webp'):
                    if create_webp(img_path, webp_path):
                        if os.path.exists(img_path) and img_path != webp_path:
                            os.remove(img_path)

                page_url = f"{BASE_URL}/{manga_folder}/{chap_folder}/{webp_name}"
                pages.append(page_url)

            if pages:
                if not cover_url:
                    cover_url = pages[0]

                chapters.append({
                    "id": chap_id,
                    "number": chap_num,
                    "title": f"Capítulo {chap_num}",
                    "pages": pages
                })

        chapters.sort(key=lambda x: x["number"])

        if chapters:
            manga_list.append({
                "id": manga_id,
                "title": manga_title,
                "category": "manhwa",
                "cover": cover_url,
                "progress": 0,
                "synopsis": "Sinopsis por defecto.",
                "chapters": chapters
            })

    # 3. Guardar el resultado final en mangas.json
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n Catálogo actualizado con éxito en '{OUTPUT_JSON}'!")
    print(f"Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
