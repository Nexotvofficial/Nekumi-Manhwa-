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

# True para usar el CDN de jsDelivr
USE_JSDELIVR = True

BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"
TOTAL_CAPITULOS = 50

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

def auto_setup_manga_folder(manga_path, manga_id):
    """Crea o actualiza info.json automático con 'featured' y gestiona carpetas cap-1 a cap-50."""
    default_title = manga_id.replace("-", " ").title()
    json_info_path = os.path.join(manga_path, "info.json")

    default_meta = {
        "title": default_title,
        "category": "manhwa",    # Opciones: manhwa, manga, manhua, fanmade
        "status": "En emisión",  # Opciones: En emisión, Finalizado, Pausado
        "featured": False,       # True solo para mostrar en la sección Destacados/Top
        "rating": 0.0,           # Puntuación o ranking opcional
        "synopsis": "Sinopsis pendiente de actualización.",
        "genres": ["Acción", "Fantasía"]
    }

    # 1. Crear info.json si no existe o añadir claves faltantes como "featured"
    if not os.path.exists(json_info_path):
        with open(json_info_path, "w", encoding="utf-8") as f:
            json.dump(default_meta, f, ensure_ascii=False, indent=2)
        print(f"📝 Plantilla 'info.json' generada automáticamente en '{manga_id}'.")
    else:
        try:
            with open(json_info_path, "r", encoding="utf-8") as f:
                current_data = json.load(f)
            
            updated = False
            for key, val in default_meta.items():
                if key not in current_data:
                    current_data[key] = val
                    updated = True
            
            if updated:
                with open(json_info_path, "w", encoding="utf-8") as f:
                    json.dump(current_data, f, ensure_ascii=False, indent=2)
                print(f"🔄 'info.json' en '{manga_id}' actualizado con campos faltantes (incluyendo 'featured').")
        except Exception as e:
            print(f"⚠️ Error actualizando info.json en {manga_id}: {e}")

    # 2. Crear carpetas cap-1 a cap-N con .gitkeep
    for c in range(1, TOTAL_CAPITULOS + 1):
        chap_path = os.path.join(manga_path, f"cap-{c}")
        os.makedirs(chap_path, exist_ok=True)

        real_images = [
            f for f in os.listdir(chap_path)
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover") and f != ".gitkeep"
        ]
        gitkeep_file = os.path.join(chap_path, ".gitkeep")

        if len(real_images) == 0:
            if not os.path.exists(gitkeep_file):
                with open(gitkeep_file, "w") as f:
                    f.write("")
        else:
            if os.path.exists(gitkeep_file):
                os.remove(gitkeep_file)

def load_manga_metadata(manga_path, default_title):
    metadata = {
        "title": default_title,
        "synopsis": "Sinopsis no disponible.",
        "status": "En emisión",
        "category": "manhwa",
        "genres": ["Acción"],
        "featured": False,
        "rating": 0.0
    }
    
    json_info = os.path.join(manga_path, "info.json")
    if os.path.exists(json_info):
        try:
            with open(json_info, "r", encoding="utf-8") as f:
                data = json.load(f)
                metadata.update(data)
        except Exception as e:
            print(f"⚠️ Error leyendo info.json en {manga_path}: {e}")
            
    if "category" in metadata:
        metadata["category"] = str(metadata["category"]).lower().strip().replace(" ", "-")
    if "status" in metadata:
        metadata["status"] = str(metadata["status"]).capitalize().strip()
        
    return metadata

def resolve_cover(manga_id):
    """Detecta portada en img/ o la toma de la primera página del capítulo 1."""
    for ext in ['.webp', '.png', '.jpg', '.jpeg']:
        c_path = os.path.join(IMG_DIR, f"{manga_id}{ext}")
        if os.path.exists(c_path):
            target = os.path.join(IMG_DIR, f"{manga_id}.webp")
            if c_path != target:
                if c_path.lower().endswith('.webp'):
                    shutil.move(c_path, target)
                else:
                    if create_webp(c_path, target):
                        os.remove(c_path)
            return get_media_url(target)

    manga_path = os.path.join(BASE_DIR, manga_id)
    if os.path.exists(manga_path):
        for ext in ['.webp', '.png', '.jpg', '.jpeg']:
            c_path = os.path.join(manga_path, f"cover{ext}")
            if os.path.exists(c_path):
                target = os.path.join(IMG_DIR, f"{manga_id}.webp")
                create_webp(c_path, target)
                return get_media_url(target)

        for chap_folder in sorted(os.listdir(manga_path), key=natural_sort_key):
            chap_path = os.path.join(manga_path, chap_folder)
            if os.path.isdir(chap_path):
                imgs = [
                    f for f in os.listdir(chap_path)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and f != ".gitkeep"
                ]
                if imgs:
                    imgs.sort(key=natural_sort_key)
                    first_img = os.path.join(chap_path, imgs[0])
                    target = os.path.join(IMG_DIR, f"{manga_id}.webp")
                    create_webp(first_img, target)
                    return get_media_url(target)

    return ""

def generate_catalog():
    print("🚀 Iniciando automatización completa...")
    auto_fix_and_organize()

    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)

    manga_ids = sorted([
        d for d in os.listdir(BASE_DIR) 
        if os.path.isdir(os.path.join(BASE_DIR, d))
    ], key=natural_sort_key)

    manga_list = []

    for manga_id in manga_ids:
        manga_path = os.path.join(BASE_DIR, manga_id)
        
        # Genera/actualiza automáticamente la estructura interna y el info.json de la obra
        auto_setup_manga_folder(manga_path, manga_id)
        
        default_title = manga_id.replace("-", " ").title()
        meta = load_manga_metadata(manga_path, default_title)

        chapters = []
        for chap_folder in sorted(os.listdir(manga_path), key=natural_sort_key):
            chap_path = os.path.join(manga_path, chap_folder)
            if not os.path.isdir(chap_path):
                continue

            raw_images = [
                f for f in os.listdir(chap_path)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover") and f != ".gitkeep"
            ]
            if not raw_images:
                continue

            images = sorted(raw_images, key=natural_sort_key)
            safe_paths = []

            for index, img_name in enumerate(images):
                img_path = os.path.join(chap_path, img_name)
                temp_path = os.path.join(chap_path, f"temp_page_{index:04d}.webp")

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
                        _, ext = os.path.splitext(img_name)
                        fallback_path = os.path.join(chap_path, f"temp_page_{index:04d}{ext}")
                        shutil.move(img_path, fallback_path)
                        safe_paths.append(fallback_path)

            pages = []
            for index, temp_path in enumerate(safe_paths):
                _, ext = os.path.splitext(temp_path)
                final_name = f"{index+1:03d}{ext}"
                final_path = os.path.join(chap_path, final_name)
                if os.path.abspath(temp_path) != os.path.abspath(final_path):
                    shutil.move(temp_path, final_path)
                pages.append(get_media_url(final_path))

            chap_num = extract_chapter_number(chap_folder)
            chapters.append({
                "id": chap_folder.lower().replace(" ", "-"),
                "number": chap_num,
                "title": f"Capítulo {chap_num}",
                "pages_count": len(pages),
                "pages": pages
            })

        chapters.sort(key=lambda x: x["number"])
        cover_url = resolve_cover(manga_id)

        if chapters or cover_url:
            manga_list.append({
                "id": manga_id,
                "title": meta.get("title", default_title),
                "category": meta.get("category", "manhwa"),
                "cover": cover_url,
                "cover_thumb": cover_url,
                "status": meta.get("status", "En emisión"),
                "featured": meta.get("featured", False),
                "rating": meta.get("rating", 0.0),
                "synopsis": meta.get("synopsis", "Sinopsis no disponible."),
                "genres": meta.get("genres", ["Acción"]),
                "total_chapters": len(chapters),
                "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "chapters": chapters
            })
            print(f"✅ [{meta.get('category').upper()}] [{meta.get('status')}] (Featured: {meta.get('featured')}) '{manga_id}' sincronizado con {len(chapters)} caps activos.")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Sincronización finalizada. '{OUTPUT_JSON}' generado con {len(manga_list)} títulos.")

if __name__ == "__main__":
    generate_catalog()
