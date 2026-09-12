import os
import json
import re
import shutil
import hashlib
from datetime import datetime
from PIL import Image
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configuración principal
BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"
CACHE_FILE = "uploaded_cache.json"
IMGBB_API_KEY = "4b0b73663ee43670cab4cec476709bb4"

# Cantidad de cargas simultáneas a ImgBB
MAX_WORKERS = 6

SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "img", "generator.py", "mangas.json", 
    "uploaded_cache.json", "README.md", "app", "build", ".gitignore", ".workflows"
}

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Error al guardar el caché: {e}")

def get_file_hash(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

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

def upload_single_task(task):
    image_path, file_hash, name = task
    url = "https://api.imgbb.com/1/upload"
    retries = 3

    for attempt in range(retries):
        try:
            with open(image_path, "rb") as file:
                payload = {"key": IMGBB_API_KEY}
                if name:
                    payload["name"] = name
                files = {"image": file}

                response = requests.post(url, data=payload, files=files, timeout=30)
                data = response.json()

                if data.get("success"):
                    direct_url = data["data"]["url"]
                    thumb_data = data["data"].get("thumb") or data["data"].get("medium")
                    thumb_url = thumb_data.get("url") if thumb_data else direct_url
                    
                    return file_hash, {"url": direct_url, "thumb": thumb_url}
                else:
                    print(f"⚠️ Reintento {attempt+1} en ImgBB para {os.path.basename(image_path)}")
                    time.sleep(2)
        except Exception as e:
            print(f"⚠️ Excepción en reintento {attempt+1}: {e}")
            time.sleep(2)

    return file_hash, None

def process_and_upload_batch(tasks_list, cache):
    if not tasks_list:
        return

    print(f"⚡ Subiendo {len(tasks_list)} imágenes en paralelo ({MAX_WORKERS} hilos simúltaneos)...")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(upload_single_task, task) for task in tasks_list]
        
        completed_count = 0
        for future in as_completed(futures):
            file_hash, result = future.result()
            if result:
                cache[file_hash] = result
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == len(tasks_list):
                    save_cache(cache)
                    print(f"⏳ Avance: {completed_count}/{len(tasks_list)} imágenes subidas.")

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
    print("🚀 Escaneando carpetas y preparando procesamiento masivo...")
    
    auto_fix_and_organize()
    cache = load_cache()

    upload_tasks = []
    file_map = {}

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
        manga_path = os.path.join(BASE_DIR, manga_id)
        
        for ext in ['.webp', '.png', '.jpg', '.jpeg']:
            cover_src = os.path.join(IMG_DIR, f"{manga_id}{ext}")
            if os.path.exists(cover_src):
                target_cover = os.path.join(IMG_DIR, f"{manga_id}.webp")
                if cover_src != target_cover:
                    if create_webp(cover_src, target_cover):
                        if os.path.exists(cover_src):
                            os.remove(cover_src)
                
                f_hash = get_file_hash(target_cover)
                file_map[target_cover] = f_hash
                if f_hash not in cache:
                    upload_tasks.append((target_cover, f_hash, f"cover_{manga_id}"))
                break

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

                for index, img_name in enumerate(images):
                    img_path = os.path.join(chap_path, img_name)
                    target_webp_name = f"{index+1:03d}.webp"
                    target_webp_path = os.path.join(chap_path, target_webp_name)

                    if os.path.abspath(img_path) != os.path.abspath(target_webp_path):
                        if create_webp(img_path, target_webp_path):
                            if os.path.exists(img_path):
                                os.remove(img_path)
                    else:
                        temp_path = os.path.join(chap_path, f"temp_{target_webp_name}")
                        if create_webp(img_path, temp_path):
                            shutil.move(temp_path, target_webp_path)

                    f_hash = get_file_hash(target_webp_path)
                    file_map[target_webp_path] = f_hash
                    if f_hash not in cache:
                        upload_tasks.append((target_webp_path, f_hash, f"{manga_id}_{chap_folder}_{index+1:03d}"))

    if upload_tasks:
        process_and_upload_batch(upload_tasks, cache)
    else:
        print("⚡ Todas las imágenes ya están registradas en el caché. Generando JSON directo...")

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

                raw_images = [
                    f for f in os.listdir(chap_path) 
                    if f.lower().endswith('.webp') and not f.startswith("cover")
                ]
                images = sorted(raw_images, key=natural_sort_key)

                pages = []
                for img_name in images:
                    target_webp_path = os.path.join(chap_path, img_name)
                    f_hash = file_map.get(target_webp_path) or (get_file_hash(target_webp_path) if os.path.exists(target_webp_path) else None)
                    
                    if f_hash and f_hash in cache:
                        pages.append(cache[f_hash]["url"])

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
        cover_hash = file_map.get(cover_path) or (get_file_hash(cover_path) if os.path.exists(cover_path) else None)
        
        cover_url, cover_thumb = "", ""
        if cover_hash and cover_hash in cache:
            cover_url = cache[cover_hash]["url"]
            cover_thumb = cache[cover_hash]["thumb"]

        manga_list.append({
            "id": manga_id,
            "title": meta["title"],
            "category": "manhwa",
            "cover": cover_url,
            "cover_thumb": cover_thumb,
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
    print(f"📊 Total de mangas en la base de datos: {len(manga_list)}")

if __name__ == "__main__":
    generate_catalog()
