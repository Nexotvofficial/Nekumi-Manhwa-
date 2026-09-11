import os
import json
import re
from PIL import Image

# Configuración de carpetas y repositorio
BASE_DIR = "catalog"  # Carpeta raíz donde guardas tus mangas
OUTPUT_JSON = "mangas.json"
BASE_URL = "https://raw.githubusercontent.com/Nexotvofficial/Nekumi-Manhwa-/main/catalog"

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
    """Detecta inteligentemente el número del capítulo desde el nombre de la carpeta"""
    # Busca números enteros o decimales (ej: cap-1, cap-02, 12.5, capitulo_3)
    match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
    if match:
        num_str = match.group(1)
        return float(num_str) if '.' in num_str else int(num_str)
    return 1

def generate_catalog():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)
        print(f"Se ha creado la carpeta '{BASE_DIR}'. Coloca ahí las carpetas de tus manhwas.")
        return

    manga_list = []

    # Recorrer cada carpeta de manhwa
    for manga_folder in sorted(os.listdir(BASE_DIR)):
        manga_path = os.path.join(BASE_DIR, manga_folder)
        if not os.path.isdir(manga_path):
            continue

        manga_id = manga_folder.lower().replace(" ", "-")
        manga_title = manga_folder.replace("-", " ").title()
        
        chapters = []
        cover_url = ""

        # Recorrer los capítulos dentro del manhwa
        for chap_folder in sorted(os.listdir(manga_path)):
            chap_path = os.path.join(manga_path, chap_folder)
            if not os.path.isdir(chap_path):
                continue

            chap_id = chap_folder.lower().replace(" ", "-")
            chap_num = extract_chapter_number(chap_folder)
            
            # Obtener y filtrar imágenes
            raw_images = [f for f in os.listdir(chap_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            
            # Ordenar las imágenes alfanuméricamente (01, 02, 03...)
            images = sorted(raw_images, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])

            pages = []
            for index, img_name in enumerate(images):
                img_path = os.path.join(chap_path, img_name)
                
                # Definir nombre webp final numerado en 3 dígitos (001.webp, 002.webp)
                webp_name = f"{index+1:03d}.webp"
                webp_path = os.path.join(chap_path, webp_name)

                # Si el archivo no es .webp, convertirlo y eliminar el original
                if not img_name.endswith('.webp'):
                    if create_webp(img_path, webp_path):
                        if os.path.exists(img_path) and img_path != webp_path:
                            os.remove(img_path)

                page_url = f"{BASE_URL}/{manga_folder}/{chap_folder}/{webp_name}"
                pages.append(page_url)

            if pages:
                # La primera página del primer capítulo servirá de portada general
                if not cover_url:
                    cover_url = pages[0]

                chapters.append({
                    "id": chap_id,
                    "number": chap_num,
                    "title": f"Capítulo {chap_num}",
                    "pages": pages
                })

        # Ordenar los capítulos numéricamente antes de guardar
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

    # Guardar el resultado en mangas.json
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n¡Catálogo generado con éxito en '{OUTPUT_JSON}'!")
    print(f"Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
