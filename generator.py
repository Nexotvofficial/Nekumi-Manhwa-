import os
import json
import re
import shutil
import hashlib
import base64
import concurrent.futures
import urllib.parse
from datetime import datetime
from PIL import Image, ImageOps

try:
    import requests
except ImportError:
    requests = None

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
# SUBIDA AUTOMÁTICA A REPOS SECUNDARIOS (almacén de capítulos)
# Cuando el info.json de un manga tiene "repo" distinto al principal,
# el script sube las imágenes procesadas directamente a ESE repo vía
# la API de Git de GitHub (un solo commit por manga), y luego borra
# la copia local para que el repo principal no acumule peso.
#
# Requiere:
#  - pip install requests
#  - Un token con permiso de escritura sobre el repo destino, en la
#    variable de entorno definida en GITHUB_TOKEN_ENV (el GITHUB_TOKEN
#    automático de Actions NO sirve para escribir en otros repos).
# Si no hay token disponible, simplemente no sube nada y avisa por
# consola (no rompe la generación del JSON).
# ------------------------------------------------------------------
ENABLE_REMOTE_UPLOAD = True
GITHUB_TOKEN_ENV = "GH_STORAGE_TOKEN"
API_BASE = "https://api.github.com"

# Número de hilos usados para conversión de imágenes y para subir blobs.
MAX_WORKERS = 8
# Reintentos automáticos para llamadas a la API de GitHub (errores transitorios).
GH_API_MAX_RETRIES = 3
GH_API_BACKOFF_FACTOR = 1.5


def _build_requests_session():
    """Crea una sesión de requests con reintentos automáticos (backoff exponencial)
    para errores transitorios de red o de la API de GitHub (429/500/502/503/504)."""
    if requests is None:
        return None
    session = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        try:
            from urllib3.util.retry import Retry
        except ImportError:
            from requests.packages.urllib3.util.retry import Retry

        retry_kwargs = dict(
            total=GH_API_MAX_RETRIES,
            backoff_factor=GH_API_BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        try:
            retry = Retry(allowed_methods=["GET", "POST", "PATCH"], **retry_kwargs)
        except TypeError:
            # Versiones viejas de urllib3 usan 'method_whitelist' en vez de 'allowed_methods'.
            retry = Retry(method_whitelist=["GET", "POST", "PATCH"], **retry_kwargs)

        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    except Exception as e:
        print(f"⚠️ No se pudo configurar reintentos automáticos para la API de GitHub: {e}")
    return session


_HTTP_SESSION = _build_requests_session()


def _atomic_write_json(path, data):
    """Escribe JSON de forma atómica (archivo temporal + reemplazo) para evitar
    dejar el archivo corrupto/incompleto si el proceso se interrumpe a mitad de escritura."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _gh_headers():
    token = os.environ.get(GITHUB_TOKEN_ENV)
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _create_blob(owner, repo, headers, local_path):
    session = _HTTP_SESSION or requests
    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")
    r = session.post(
        f"{API_BASE}/repos/{owner}/{repo}/git/blobs",
        headers=headers,
        json={"content": content_b64, "encoding": "base64"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["sha"]


def push_files_to_repo(repo_name, file_map, commit_message, owner=GITHUB_USER, branch=BRANCH):
    """Sube en UN SOLO commit todos los archivos de file_map = {ruta_remota: ruta_local}."""
    if not file_map:
        return True
    if requests is None:
        print("⚠️ Falta el paquete 'requests' (pip install requests). No se sube nada a repos remotos.")
        return False

    headers = _gh_headers()
    if not headers:
        print(f"⚠️ No hay token en la variable de entorno '{GITHUB_TOKEN_ENV}'. Se omite la subida a '{repo_name}' (se reintentará en la próxima corrida).")
        return False

    session = _HTTP_SESSION or requests

    try:
        ref = session.get(f"{API_BASE}/repos/{owner}/{repo_name}/git/ref/heads/{branch}", headers=headers, timeout=30)
        ref.raise_for_status()
        base_commit_sha = ref.json()["object"]["sha"]

        base_commit = session.get(f"{API_BASE}/repos/{owner}/{repo_name}/git/commits/{base_commit_sha}", headers=headers, timeout=30)
        base_commit.raise_for_status()
        base_tree_sha = base_commit.json()["tree"]["sha"]

        tree_entries = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(_create_blob, owner, repo_name, headers, local_path): remote_path
                for remote_path, local_path in file_map.items()
            }
            for future in concurrent.futures.as_completed(future_map):
                remote_path = future_map[future]
                blob_sha = future.result()
                tree_entries.append({"path": remote_path, "mode": "100644", "type": "blob", "sha": blob_sha})

        new_tree = session.post(
            f"{API_BASE}/repos/{owner}/{repo_name}/git/trees", headers=headers,
            json={"base_tree": base_tree_sha, "tree": tree_entries}, timeout=60
        )
        new_tree.raise_for_status()

        new_commit = session.post(
            f"{API_BASE}/repos/{owner}/{repo_name}/git/commits", headers=headers,
            json={"message": commit_message, "tree": new_tree.json()["sha"], "parents": [base_commit_sha]}, timeout=30
        )
        new_commit.raise_for_status()

        patch = session.patch(
            f"{API_BASE}/repos/{owner}/{repo_name}/git/refs/heads/{branch}", headers=headers,
            json={"sha": new_commit.json()["sha"]}, timeout=30
        )
        patch.raise_for_status()

        print(f"☁️  Subidas {len(tree_entries)} imagen(es) a '{repo_name}' en un solo commit.")
        return True
    except Exception as e:
        print(f"❌ Error subiendo a '{repo_name}': {e}")
        return False


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
        with Image.open(input_path) as raw_img:
            # Corrige orientación según metadata EXIF (fotos/escaneos girados por cámara/escáner).
            # No afecta a imágenes que ya vienen bien orientadas o sin metadata EXIF.
            pil_img = ImageOps.exif_transpose(raw_img)
            pil_img = pil_img.convert("RGB")
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
        _atomic_write_json(CACHE_FILE, cache)
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
        _atomic_write_json(json_info_path, default_meta)
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
                _atomic_write_json(json_info_path, current_data)
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


# Páginas que un scan insertó (créditos, staff, publicidad de Discord/Patreon, etc.)
# se detectan por el nombre de archivo ORIGINAL (antes de renombrarlas a 001.webp...).
# También se puede forzar manualmente creando "extra_pages.txt" dentro de la carpeta
# del capítulo, con un nombre de archivo por línea (tal cual está en esa carpeta).
EXTRA_PAGE_KEYWORDS = re.compile(
    r'(extra|credito|creditos|staff|traductor|traduccion|publicidad|donacion|discord|patreon|anuncio)',
    re.IGNORECASE,
)


def _load_manual_extra_list(chap_path):
    manual_path = os.path.join(chap_path, "extra_pages.txt")
    if not os.path.exists(manual_path):
        return set()
    try:
        with open(manual_path, "r", encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip()}
    except Exception as e:
        print(f"⚠️ No se pudo leer extra_pages.txt en {chap_path}: {e}")
        return set()


def _compute_extra_flags(chap_path, images):
    manual_extra = _load_manual_extra_list(chap_path)
    return [
        bool(EXTRA_PAGE_KEYWORDS.search(os.path.splitext(name)[0])) or name.lower() in manual_extra
        for name in images
    ]


def _convert_chapter_images(chap_path, images):
    """Convierte las imágenes de un capítulo a WebP en paralelo (hilos), preservando
    el orden original de páginas. Devuelve la lista de rutas finales temporales
    (safe_paths) en el mismo orden que 'images'."""
    safe_paths = [None] * len(images)
    conversion_tasks = []  # (index, img_name, img_path, temp_path)

    for index, img_name in enumerate(images):
        img_path = os.path.join(chap_path, img_name)
        temp_path = os.path.join(chap_path, f"temp_page_{index:04d}.webp")

        if img_name.lower().endswith('.webp'):
            if os.path.abspath(img_path) != os.path.abspath(temp_path):
                shutil.move(img_path, temp_path)
            safe_paths[index] = temp_path
        else:
            conversion_tasks.append((index, img_name, img_path, temp_path))

    if conversion_tasks:
        workers = min(MAX_WORKERS, len(conversion_tasks))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(create_webp, img_path, temp_path): (index, img_name, img_path, temp_path)
                for (index, img_name, img_path, temp_path) in conversion_tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                index, img_name, img_path, temp_path = future_map[future]
                try:
                    ok = future.result()
                except Exception as e:
                    print(f"❌ Error inesperado procesando {img_path}: {e}")
                    ok = False

                if ok:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                    safe_paths[index] = temp_path
                else:
                    # Mismo comportamiento de fallback que antes: si la conversión falla,
                    # se conserva el archivo original tal cual (no se borra la imagen).
                    _, ext = os.path.splitext(img_name)
                    fallback_path = os.path.join(chap_path, f"temp_page_{index:04d}{ext}")
                    shutil.move(img_path, fallback_path)
                    safe_paths[index] = fallback_path

    return safe_paths


def process_manga(manga_id, manga_path, prev_cache):
    """Pipeline completo para un manga (solo corre cuando el cache indica cambios).
    prev_cache: lo que había guardado para este manga_id en uploaded_cache.json
    (se usa para no perder capítulos que ya se subieron y se borraron localmente)."""
    auto_setup_manga_folder(manga_path, manga_id)

    default_title = manga_id.replace("-", " ").title()
    meta = load_manga_metadata(manga_path, default_title)
    manga_repo = meta.get("repo", GITHUB_REPO)
    remote_mode = ENABLE_REMOTE_UPLOAD and manga_repo != GITHUB_REPO

    prev_chapters_cache = (prev_cache or {}).get("chapters", {})
    new_chapters_cache = {}
    pending_uploads = {}  # ruta_remota -> ruta_local

    chap_folders_disk = [
        d for d in os.listdir(manga_path) if os.path.isdir(os.path.join(manga_path, d))
    ]
    # Unimos con lo que ya conocíamos por cache, por si la carpeta local
    # quedó vacía/borrada tras una subida anterior.
    all_chap_keys = sorted(set(chap_folders_disk) | set(prev_chapters_cache.keys()), key=natural_sort_key)

    chapters = []
    for chap_folder in all_chap_keys:
        chap_path = os.path.join(manga_path, chap_folder)

        raw_images = []
        if os.path.isdir(chap_path):
            raw_images = [
                f for f in os.listdir(chap_path)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.startswith("cover") and f != ".gitkeep"
            ]

        if not raw_images:
            # No hay nada nuevo localmente: reutiliza lo ya conocido (probablemente ya subido).
            cached_chap = prev_chapters_cache.get(chap_folder)
            if cached_chap:
                chapters.append(cached_chap)
                new_chapters_cache[chap_folder] = cached_chap
            continue

        images = sorted(raw_images, key=natural_sort_key)
        extra_flags = _compute_extra_flags(chap_path, images)
        safe_paths = _convert_chapter_images(chap_path, images)

        pages = []
        final_paths = []
        for index, temp_path in enumerate(safe_paths):
            _, ext = os.path.splitext(temp_path)
            final_name = f"{index+1:03d}{ext}"
            final_path = os.path.join(chap_path, final_name)
            if os.path.abspath(temp_path) != os.path.abspath(final_path):
                shutil.move(temp_path, final_path)

            final_paths.append(final_path)
            page_url = get_media_url(final_path, repo_name=manga_repo)
            if extra_flags[index]:
                pages.append({"url": page_url, "extra": True})
            else:
                pages.append(page_url)

        if remote_mode:
            for final_path in final_paths:
                remote_rel = final_path.replace("\\", "/")
                pending_uploads[remote_rel] = final_path

        chap_num = extract_chapter_number(chap_folder)
        real_pages_count = sum(1 for flag in extra_flags if not flag) or len(pages)
        chapter_data = {
            "id": chap_folder.lower().replace(" ", "-"),
            "number": chap_num,
            "title": f"Capítulo {chap_num}",
            "pages_count": real_pages_count,
            "pages": pages
        }
        chapters.append(chapter_data)
        new_chapters_cache[chap_folder] = chapter_data

    chapters.sort(key=lambda x: x["number"])

    # Portada: si hay una nueva localmente la procesa; si no, reutiliza la que ya se conocía.
    has_local_cover_source = any(
        os.path.exists(os.path.join(IMG_DIR, f"{manga_id}{ext}")) or
        os.path.exists(os.path.join(manga_path, f"cover{ext}"))
        for ext in ('.webp', '.png', '.jpg', '.jpeg')
    )
    prev_cover_url = (prev_cache or {}).get("cover_url", "")

    if has_local_cover_source or not prev_cover_url:
        cover_url = resolve_cover(manga_id, repo_name=manga_repo)
        cover_target = os.path.join(IMG_DIR, f"{manga_id}.webp")
        if remote_mode and os.path.exists(cover_target):
            pending_uploads[cover_target.replace("\\", "/")] = cover_target
    else:
        cover_url = prev_cover_url

    if remote_mode and pending_uploads:
        ok = push_files_to_repo(manga_repo, pending_uploads, f"Auto: capítulos/portada de {manga_id}")
        if ok:
            for local_path in pending_uploads.values():
                try:
                    os.remove(local_path)
                except OSError:
                    pass
        # si falla, se deja todo local para reintentar en la próxima corrida

    if not (chapters or cover_url):
        return None, None

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
    manga_cache_out = {"cover_url": cover_url, "chapters": new_chapters_cache}
    print(f"✅ [{meta.get('category').upper()}] [{meta.get('status')}] (Repo: {manga_repo}) "
          f"'{manga_id}' sincronizado con {len(chapters)} caps activos.")
    return entry, manga_cache_out


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

        # 2. Cache miss -> procesar (usa el cache previo para no perder caps ya subidos)
        try:
            entry, manga_cache_out = process_manga(manga_id, manga_path, cached)
        except Exception as e:
            print(f"❌ Error procesando '{manga_id}', se omite en esta corrida: {e}")
            # Si había una entrada válida en cache previo, la conservamos para no perderla.
            if cached and cached.get("entry"):
                manga_list.append(cached["entry"])
                new_cache[manga_id] = cached
            continue

        if entry:
            manga_list.append(entry)
            signature_after = compute_manga_signature(manga_id, manga_path)
            manga_cache_out["signature"] = signature_after
            manga_cache_out["entry"] = entry
            new_cache[manga_id] = manga_cache_out

    _atomic_write_json(OUTPUT_JSON, manga_list)

    save_cache(new_cache)

    print(f"\n🎉 Sincronización finalizada. '{OUTPUT_JSON}' generado con {len(manga_list)} títulos "
          f"({reused} reutilizados desde cache, {len(manga_list) - reused} reprocesados).")


if __name__ == "__main__":
    generate_catalog()
