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

# Porcentaje de recorte para eliminar marcas de agua en bordes superior e inferior (0.0 = sin recorte)
TOP_CROP_PERCENT = 0.02    # Recorta el 2% superior de la imagen
BOTTOM_CROP_PERCENT = 0.02 # Recorta el 2% inferior de la imagen

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

def remove_watermark_and_crop(img, top_percent=TOP_CROP_PERCENT, bottom_percent=BOTTOM_CROP_PERCENT):
    """
    Elimina marcas de agua recortando bordes superior e inferior de la imagen.
    """
    width, height = img.size
    
    # Calcular coordenadas para el recorte
    top = int(height * top_percent)
    bottom = int(height * (1 - bottom_percent))
    
    if top < bottom and (top > 0 or bottom < height):
        return img.crop((0, top, width, bottom))
    
    return img

def create_webp(input_path, output_path, quality=80, is_page=False):
    """Convierte, remueve marcas de agua y optimiza imágenes a WebP"""
    try:
        # Si el archivo origen y destino son diferentes o se requiere recortar marca de agua
        with Image.open(input_path) as img:
            img = img.convert("RGB")
            
            if is_page:
                img = remove_watermark_and_crop(img)
            
            # Crear directorio destino si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, "WEBP", quality=quality)
            
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
    Busca únicamente la portada en la carpeta img/ asociada al ID del manhwa.
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
            return f"{IMG_BASE_URL}/{manga_id}.webp"

    return ""

def generate_catalog():
    print("🚀 Iniciando generación automática de catálogo...")
    
    auto_fix_and_organize()

    manga_list = []
    
    # 1. Obtener los IDs desde las carpetas dentro de catalog/
    catalog_mangas = set()
    if os.path.exists(BASE_DIR):
        for f in os.listdir(BASE_DIR):
            if os.path.isdir(os.path.join(BASE_DIR, f)):
                catalog_mangas.add(f.lower().replace(" ", "-"))

    # 2. Obtener los IDs desde las imágenes de portada dentro de img/
    img_mangas = set()
    if os.path.exists(IMG_DIR):
        for f in os.listdir(IMG_DIR):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                name_without_ext = os.path.splitext(f)[0]
                img_mangas.add(name_without_ext.lower().replace(" ", "-"))

    # 3. Unir ambos para procesar todos los manhwas detectados
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

                    # Si el archivo original no es la ruta final WebP numerada
                    if os.path.abspath(img_path) != os.path.abspath(target_webp_path):
                        if create_webp(img_path, target_webp_path, is_page=True):
                            if os.path.exists(img_path):
                                os.remove(img_path)
                    else:
                        # Si ya es el archivo final .webp, se procesa a un temporal y se reemplaza
                        temp_path = os.path.join(chap_path, f"temp_{target_webp_name}")
                        if create_webp(img_path, temp_path, is_page=True):
                            shutil.move(temp_path, target_webp_path)

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
