import os
import json
import re
import shutil
import hashlib
import urllib.parse
from datetime import datetime
from PIL import Image

# Configuración del Repositorio de GitHub Predeterminado
GITHUB_USER = "Nexotvofficial"
GITHUB_REPO = "Nekumi-Manhwa-"
BRANCH = "main"

# True para usar el CDN de jsDelivr
USE_JSDELIVR = True

BASE_DIR = "catalog"
IMG_DIR = "img"
OUTPUT_JSON = "mangas.json"
CACHE_FILE = "uploaded_cache.json"
TOTAL_CAPITULOS = 50          # tope absoluto de seguridad
CHAPTER_BUFFER = 3            # carpetas vacías extra que se mantienen listas para el próximo capítulo

SYSTEM_ITEMS = {
    ".github", ".git", "catalog", "img", "generator.py", "mangas.json",
    "uploaded_cache.json", "README.md", "app", "build", ".gitignore", ".workflows"
}

# ------------------------------------------------------------------
# IMPORTANTE SOBRE MULTI-REPO:
# El campo "repo" en info.json solo cambia la URL que se genera
# (cdn.jsdelivr.net/gh/USER/ESE_REPO@main/...). El script NO copia ni
# sube archivos a ese otro repositorio. Para que un manga "viva" en
# otro repo de verdad, ese repo tiene que contener físicamente la
# misma ruta catalog/<manga_id>/cap-X/... — normalmente esto se logra
# agregándolo como git submodule dentro de catalog/<manga_id>, o con
# un paso adicional que haga push vía API de GitHub. Si el repo no
# tiene esos archivos, la URL generada dará 404 aunque el JSON se vea
# perfecto.
# ------------------------------------------------------------------


def get_media_url(file_path, repo_name=GITHUB_REPO):
    """Genera la URL del CDN soportando múltiples repositorios dinámicamente."""
    clean_path = file_path.replace("\\", "/")
    clean_path = urllib.parse.quote(clean_path, safe='/')
    if USE_JSDELIVR:
        return f"https://cdn.jsdelivr.net/gh/{GITHUB_USER}/{repo_name}@{BRANCH}/{clean_path}"
    return f"https://raw.githubusercontent.com/{GITHUB_USER}/{repo_name}/{BRANCH}/{clean_path}"


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


# ---------------------- CACHE (nuevo) ----------------------

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ No se pudo leer {CACHE_FILE}, se ignora el cache: {e}")
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ No se pudo guardar {CACHE_FILE}: {e}")


def compute_manga_signature(manga_id, manga_path):
    """Firma rápida (sin abrir imágenes) para saber si algo cambió desde la última corrida."""
    parts = []
    for root, dirs, files in os.walk(manga_path):
        dirs.sort()
        for fname in sorted(files):
            if fname == ".gitkeep":
                continue
            fpath = os.path.join(root, fname)
            try:
                st = os.stat(fpath)
                parts.append(f"{fpath}:{st.st_size}:{int(st.st_mtime)}")
            except OSError:
                continue

    for ext in ('.webp', '.png', '.jpg', '.jpeg'):
        cover_path = os.path.join(IMG_DIR, f"{manga_id}{ext}")
        if os.path.exists(cover_path):
            st = os.stat(cover_path)
            parts.append(f"{cover_path}:{st.st_size}:{int(st.st_mtime)}")

    raw = "|".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


# ---------------------- SETUP DE CARPETAS (optimizado) ----------------------

def auto_setup_manga_folder(manga_path, manga_id):
    """Crea/actualiza info.json y solo el colchón de carpetas de capítulos necesario
    (en vez de siempre 1..TOTAL_CAPITULOS), y limpia carpetas vacías sobrantes."""
    default_title = manga_id.replace("-", " ").title()
    json_info_path = os.path.join(manga_path, "info.json")

    default_meta = {
        "title": default_title,
        "category": "manhwa",
        "status": "En emisión",
        "featured": False,
        "rating": 0.0,
        "synopsis": "Sinopsis pendiente de actualización.",
        "genres": ["Acción", "Fantasía"],
        "repo": GITHUB_REPO
    }

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
                print(f"🔄 'info.json' en '{manga_id}' actualizado con campos faltantes.")
        except Exception as e:
            print(f"⚠️ Error actualizando info.json en {manga_id}: {e}")

    # Detectar hasta qué capítulo hay contenido real
    existing_chaps = [
        d for d in os.listdir(manga_path)
        if os.path.isdir(os.path.join(manga_path, d)) and d.lower().startswith("cap")
    ]

    max_with_content = 0
    for chap_folder in existing_chaps:
        chap_path = os.path.join(manga_path, chap_folder)
        has_real_images = any(
            f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover") and f != ".gitkeep"
            for f in os.listdir(chap_path)
        )
        if has_real_images:
            max_with_content = max(max_with_content, int(extract_chapter_number(chap_folder)))

    limit = max(1, min(TOTAL_CAPITULOS, max_with_content + CHAPTER_BUFFER))

    # Crear solo hasta 'limit' (antes se creaban siempre las 50)
    for c in range(1, limit + 1):
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

    # Limpieza: borra carpetas vacías sobrantes de corridas viejas (con TOTAL_CAPITULOS=50 fijo)
    for chap_folder in existing_chaps:
        num = int(extract_chapter_number(chap_folder))
        if num > limit:
            chap_path = os.path.join(manga_path, chap_folder)
            try:
                contents = os.listdir(chap_path)
            except OSError:
                continue
            only_gitkeep = contents in ([], [".gitkeep"])
            if only_gitkeep:
                shutil.rmtree(chap_path, ignore_errors=True)


def load_manga_metadata(manga_path, default_title):
    metadata = {
        "title": default_title,
        "synopsis": "Sinopsis no disponible.",
        "status": "En emisión",
        "category": "manhwa",
        "genres": ["Acción"],
        "featured": False,
        "rating": 0.0,
        "repo": GITHUB_REPO
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


def resolve_cover(manga_id, repo_name=GITHUB_REPO):
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
            return get_media_url(target, repo_name=repo_name)

    manga_path = os.path.join(BASE_DIR, manga_id)
    if os.path.exists(manga_path):
        for ext in ['.webp', '.png', '.jpg', '.jpeg']:
            c_path = os.path.join(manga_path, f"cover{ext}")
            if os.path.exists(c_path):
                target = os.path.join(IMG_DIR, f"{manga_id}.webp")
                create_webp(c_path, target)
                return get_media_url(target, repo_name=repo_name)

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
                    return get_media_url(target, repo_name=repo_name)

    return ""


def process_manga(manga_id, manga_path):
    """Pipeline completo para un manga (solo corre cuando el cache indica cambios)."""
    auto_setup_manga_folder(manga_path, manga_id)

    default_title = manga_id.replace("-", " ").title()
    meta = load_manga_metadata(manga_path, default_title)
    manga_repo = meta.get("repo", GITHUB_REPO)

    if manga_repo != GITHUB_REPO:
        print(f"   ↪️  '{manga_id}' usa repo '{manga_repo}'. Verifica que ESE repo tenga físicamente "
              f"la ruta catalog/{manga_id}/... (submodule o subida manual), o las imágenes darán 404.")

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

            pages.append(get_media_url(final_path, repo_name=manga_repo))

        chap_num = extract_chapter_number(chap_folder)
        chapters.append({
            "id": chap_folder.lower().replace(" ", "-"),
            "number": chap_num,
            "title": f"Capítulo {chap_num}",
            "pages_count": len(pages),
            "pages": pages
        })

    chapters.sort(key=lambda x: x["number"])
    cover_url = resolve_cover(manga_id, repo_name=manga_repo)

    if not (chapters or cover_url):
        return None

    entry = {
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
        "repo": manga_repo,
        "total_chapters": len(chapters),
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "chapters": chapters
    }
    print(f"✅ [{meta.get('category').upper()}] [{meta.get('status')}] (Repo: {manga_repo}) "
          f"'{manga_id}' sincronizado con {len(chapters)} caps activos.")
    return entry


def generate_catalog():
    print("🚀 Iniciando automatización completa con soporte Multi-Repo (con cache)...")
    auto_fix_and_organize()

    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)

    manga_ids = sorted([
        d for d in os.listdir(BASE_DIR)
        if os.path.isdir(os.path.join(BASE_DIR, d))
    ], key=natural_sort_key)

    old_cache = load_cache()
    new_cache = {}
    manga_list = []
    reused = 0

    for manga_id in manga_ids:
        manga_path = os.path.join(BASE_DIR, manga_id)

        # 1. Firma "antes" de procesar, para ver si algo cambió desde la última corrida
        signature_before = compute_manga_signature(manga_id, manga_path)
        cached = old_cache.get(manga_id)

        if cached and cached.get("signature") == signature_before and cached.get("entry"):
            manga_list.append(cached["entry"])
            new_cache[manga_id] = cached
            reused += 1
            print(f"⚡ [CACHE] '{manga_id}' sin cambios, se reutiliza el resultado anterior.")
            continue

        # 2. Cache miss -> procesar de verdad
        entry = process_manga(manga_id, manga_path)
        if entry:
            manga_list.append(entry)
            signature_after = compute_manga_signature(manga_id, manga_path)
            new_cache[manga_id] = {"signature": signature_after, "entry": entry}

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(manga_list, f, ensure_ascii=False, indent=2)

    save_cache(new_cache)

    print(f"\n🎉 Sincronización finalizada. '{OUTPUT_JSON}' generado con {len(manga_list)} títulos "
          f"({reused} reutilizados desde cache, {len(manga_list) - reused} reprocesados).")


if __name__ == "__main__":
    generate_catalog()
