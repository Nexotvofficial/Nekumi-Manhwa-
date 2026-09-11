import os
import json
from PIL import Image

# Configuración de carpetas y servidor
BASE_DIR = "catalog"  # Carpeta raíz donde guardas tus mangas
OUTPUT_JSON = "mangas.json"
BASE_URL = "https://raw.githubusercontent.com/tu-usuario/tu-repo/main/catalog"

def create_webp(input_path, output_path, quality=80):
    """Convierte y optimiza imágenes a formato WebP"""
    try:
        with Image.open(input_path) as img:
            img.convert("RGB").save(output_path, "WEBP", quality=quality)
        return True
    except Exception as e:
        print(f"Error procesando {input_path}: {e}")
        return False

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
            pages = []

            # Filtrar y ordenar imágenes
            images = [f for f in sorted(os.listdir(chap_path)) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]

            for index, img_name in enumerate(images):
                img_path = os.path.join(chap_path, img_name)
                
                # Convertir la imagen a .webp si no lo es
                webp_name = f"{index+1:03d}.webp"
                webp_path = os.path.join(chap_path, webp_name)

                if not img_name.endswith('.webp'):
                    if create_webp(img_path, webp_path):
                        os.remove(img_path)  # Elimina el JPG/PNG original para ahorrar espacio

                page_url = f"{BASE_URL}/{manga_folder}/{chap_folder}/{webp_name}"
                pages.append(page_url)

                # Usar la primera imagen del Capítulo 1 como portada si no hay una asignada
                if not cover_url and len(pages) > 0:
                    cover_url = pages[0]

            if pages:
                # Extraer número de capítulo
                chap_num = ''.join(filter(str.isdigit, chap_folder)) or "1"
                chapters.append({
                    "id": chap_id,
                    "number": int(chap_num),
                    "title": f"Capítulo {chap_num}",
                    "pages": pages
                })

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

    # Guardar en mangas.json con formato limpio
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n¡Catálogo generado con éxito en '{OUTPUT_JSON}'!")
    print(f"Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
