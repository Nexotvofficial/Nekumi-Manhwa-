import os
import json
import re
import shutil
from datetime import datetime
from PIL import Image

# Configuración principal
BASE_DIR = "catalog"
OUTPUT_JSON = "mangas.json"
BASE_URL = "https://raw.githubusercontent.com/Nexotvofficial/Nekumi-Manhwa-/main/catalog"

# Elementos del sistema a ignorar en la raíz
SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "generator.py", "mangas.json", 
    "README.md", "app", "build", ".gitignore"
}

def auto_fix_and_organize():
    """
    Anticipa y corrige errores de estructura de archivos/carpetas subidos por el usuario.
    """
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)

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

    # 2. Corregir imágenes sueltas que hayan quedado directamente dentro de catalog/
    loose_images = [
        f for f in os.listdir(BASE_DIR) 
        if os.path.isfile(os.path.join(BASE_DIR, f)) and f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
    ]
    
    if loose_images:
        # Detectar la carpeta de manhwa más reciente o usar una por defecto
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
    """Extrae el número de capítulo incluso en nombres complejos (ej: cap-01.5, ch_10)"""
    match = re.search(r'(\d+(?:\.\d+)?)', folder_name)
    if match:
        num_str = match.group(1)
        return float(num_str) if '.' in num_str else int(num_str)
    return 1

def natural_sort_key(s):
    """Ordenamiento natural para que '2.webp' vaya antes que '10.webp'"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def load_manga_metadata(manga_path, default_title):
    """
    Futuro-Proof: Carga datos de sinopsis, estado y géneros si existe un info.json o info.txt
    """
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

def generate_catalog():
    print("🚀 Iniciando generación automática de catálogo...")
    
    # 1. Ejecutar auto-reparador de carpetas y archivos
    auto_fix_and_organize()

    manga_list = []

    # 2. Recorrer manhwas
    for manga_folder in sorted(os.listdir(BASE_DIR)):
        manga_path = os.path.join(BASE_DIR, manga_folder)
        if not os.path.isdir(manga_path):
            continue

        manga_id = manga_folder.lower().replace(" ", "-")
        default_title = manga_folder.replace("-", " ").title()
        
        # Cargar metadatos extendidos
        meta = load_manga_metadata(manga_path, default_title)

        chapters = []
        custom_cover_url = ""

        # Comprobar si existe una portada dedicada en la raíz del manhwa (cover.png / cover.jpg / cover.webp)
        for ext in ['.webp', '.png', '.jpg', '.jpeg']:
            possible_cover = f"cover{ext}"
            if os.path.exists(os.path.join(manga_path, possible_cover)):
                custom_cover_url = f"{BASE_URL}/{manga_folder}/{possible_cover}"
                break

        # Recorrer capítulos del manhwa
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
                webp_name = f"{index+1:03d}.webp"
                webp_path = os.path.join(chap_path, webp_name)

                # Convertir a WebP si es necesario
                if not img_name.endswith('.webp'):
                    if create_webp(img_path, webp_path):
                        if os.path.exists(img_path) and img_path != webp_path:
                            os.remove(img_path)

                page_url = f"{BASE_URL}/{manga_folder}/{chap_folder}/{webp_name}"
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
            # Si no hay portada personalizada, usa la primera página del capítulo 1
            final_cover = custom_cover_url if custom_cover_url else chapters[0]["pages"][0]

            manga_list.append({
                "id": manga_id,
                "title": meta["title"],
                "category": "manhwa",
                "cover": final_cover,
                "status": meta.get("status", "En emisión"),
                "synopsis": meta.get("synopsis", "Sinopsis no disponible."),
                "genres": meta.get("genres", ["Manhwa"]),
                "total_chapters": len(chapters),
                "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "chapters": chapters
            })

    # Output final con codificación UTF-8
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Catálogo generado con éxito en '{OUTPUT_JSON}'")
    print(f"📊 Total de manhwas procesados: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
