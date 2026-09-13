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

def ensure_structure_and_gitkeep():
    """Garantiza la existencia de carpetas cap-1 a cap-50 e ignora .gitkeep si hay imágenes."""
    if not os.path.exists(BASE_DIR):
        return

    for manga_name in os.listdir(BASE_DIR):
        manga_path = os.path.join(BASE_DIR, manga_name)
        if not os.path.isdir(manga_path):
            continue

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

def resolve_cover(manga_id):
    """Busca o genera la portada automáticamente para evitar la omisión del manhwa."""
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
    print("🚀 Iniciando optimización y generación del catálogo...")
    auto_fix_and_organize()
    ensure_structure_and_gitkeep()

    manga_list = []
    if not os.path.exists(BASE_DIR):
        print("⚠️ No existe la carpeta catalog/")
        return

    manga_ids = sorted([
        d for d in os.listdir(BASE_DIR) 
        if os.path.isdir(os.path.join(BASE_DIR, d))
    ], key=natural_sort_key)

    for manga_id in manga_ids:
        manga_path = os.path.join(BASE_DIR, manga_id)
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
        default_title = manga_id.replace("-", " ").title()

        if chapters or cover_url:
            manga_list.append({
                "id": manga_id,
                "title": default_title,
                "category": "manhwa",
                "cover": cover_url,
                "cover_thumb": cover_url,
                "status": "En emisión",
                "synopsis": "Sinopsis no disponible.",
                "genres": ["Manhwa", "Acción"],
                "total_chapters": len(chapters),
                "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "chapters": chapters
            })
            print(f"✅ [Procesado] '{manga_id}' con {len(chapters)} capítulos activos.")

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 ¡Catálogo generado exitosamente! '{OUTPUT_JSON}' incluye {len(manga_list)} manhwas.")

if __name__ == "__main__":
    generate_catalog()
