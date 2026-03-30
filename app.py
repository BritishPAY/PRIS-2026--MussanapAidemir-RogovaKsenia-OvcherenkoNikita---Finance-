import sys, hashlib, json, threading, uuid, time
from pathlib import Path
from flask import Flask, request, jsonify, send_file


_ui_dir  = Path(__file__).resolve().parent
_root    = _ui_dir.parent
_src_dir = _root / "src"
_html    = _ui_dir / "receipt-analytics.html"

_data_dir   = _root / "data" / "receipts"
_parsed_dir = _root / "processed" / "parsed_data"
_stats_file = _root / "processed" / "stats" / "overall_statistics.json"

for _p in [_src_dir, _root]:
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from ocr import extract_text_from_receipt
    OCR_AVAILABLE = True
    print(f"[OK] ocr.py (easyocr)")
except ImportError as e:
    OCR_AVAILABLE = False
    print(f"[WARN] ocr.py: {e}")

try:
    from parser import parse_receipt_text, save_parsed_data
    from categorizer import categorize_items, update_json_with_categories
    PARSER_AVAILABLE = True
    print(f"[OK] parser.py + categorizer.py")
except ImportError as e:
    PARSER_AVAILABLE = False
    print(f"[WARN] parser/categorizer: {e}")

try:
    from stats import compute_overall_statistics
    STATS_AVAILABLE = True
    print("[OK] stats.py")
except ImportError as e:
    STATS_AVAILABLE = False
    print(f"[WARN] stats.py: {e}")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2 GB

UPLOAD_DIR = _ui_dir / "uploads_ui"
UPLOAD_DIR.mkdir(exist_ok=True)

_jobs: dict = {}
_jobs_lock = threading.Lock()



def _update_job(job_id, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)


def _pipeline_worker(job_id: str, img_paths: list):
    log = []
    total = len(img_paths)

    def log_msg(msg):
        log.append(msg)
        print(f"[job {job_id[:6]}] {msg}")

    try:
        _update_job(job_id, status="running", step="ocr",
                    progress=0, log=list(log))

        processed = 0
        errors = 0

        for i, img_path in enumerate(img_paths):
            name = img_path.name
            pct = int((i / total) * 90)

            log_msg(f"[{i+1}/{total}] OCR: {name}")
            _update_job(job_id, step="ocr", progress=pct,
                        current_file=name, log=list(log))
            try:
                text, txt_path = extract_text_from_receipt(str(img_path))
            except Exception as e:
                log_msg(f"  ✗ OCR ошибка: {e}")
                errors += 1
                continue

            if not text.strip():
                log_msg("  ⚠ пустой текст — пропускаем")
                continue

            log_msg(f"[{i+1}/{total}] Парсинг: {name}")
            _update_job(job_id, step="parse", progress=pct,
                        current_file=name, log=list(log))
            try:
                items, receipt_total = parse_receipt_text(text)
                json_path = save_parsed_data(items, receipt_total, txt_path)
            except Exception as e:
                log_msg(f"  ✗ Парсинг ошибка: {e}")
                errors += 1
                continue

            try:
                categorized = categorize_items(items)
                update_json_with_categories(json_path, categorized)
                log_msg(f"  ✓ {len(categorized)} позиций, итог ${receipt_total:.2f}")
                processed += 1
            except Exception as e:
                log_msg(f"  ✗ Категоризация ошибка: {e}")
                errors += 1

        log_msg("Генерация итоговой статистики...")
        _update_job(job_id, step="stats", progress=92, log=list(log))

        try:
            stats_result, out_path = compute_overall_statistics()
            log_msg(f"✅ Готово! Обработано: {processed}, ошибок: {errors}")
            log_msg(f"   Сохранено → {out_path}")
        except Exception as e:
            log_msg(f"✗ Ошибка статистики: {e}")
            stats_result = {}

        _update_job(job_id, status="done", step="done", progress=100,
                    log=list(log), result=stats_result)

    except Exception as e:
        log_msg(f"❌ Критическая ошибка: {e}")
        _update_job(job_id, status="error", log=list(log), error=str(e))


@app.route("/")
def index():
    if not _html.exists():
        return f"<h2>Файл не найден:</h2><code>{_html}</code>", 404
    return send_file(_html)


@app.route("/api/load_processed")
def load_processed():
    receipts = []
    if _parsed_dir.exists():
        for jf in sorted(_parsed_dir.glob("*.json")):
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
                items = d.get("categorized_items") or d.get("items") or []
                normalized = [{
                    "name":       it.get("name", ""),
                    "qty":        it.get("qty", 1),
                    "unit_price": it.get("unit_price", 0),
                    "price":      it.get("price", 0),
                    "category":   it.get("category", "other"),
                } for it in items]
                receipts.append({
                    "id":     jf.stem,
                    "name":   jf.name,
                    "type":   "processed",
                    "items":  normalized,
                    "total":  round(float(d.get("total", 0)), 2),
                    "status": "ok" if normalized else "empty",
                })
            except Exception as e:
                print(f"[WARN] {jf.name}: {e}")

    stats_data = {}
    if _stats_file.exists():
        try:
            stats_data = json.loads(_stats_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] overall_statistics.json: {e}")

    food_cats = {"meat", "fish", "vegetables", "fruits", "dairy", "bakery",
                 "beverages", "snacks", "sweets", "restaurant_food"}
    groceries_sum = sum(
        v for k, v in stats_data.get("by_category", {}).items()
        if k in food_cats
    )

    return jsonify({
        "receipts":          receipts,
        "stats":             stats_data,
        "groceries_suggest": round(groceries_sum, 2),
        "parsed_dir_exists": _parsed_dir.exists(),
        "stats_file_exists": _stats_file.exists(),
        "receipt_count":     stats_data.get("receipt_count", len(receipts)),
        "grand_total":       stats_data.get("grand_total", 0),
        "by_category":       stats_data.get("by_category", {}),
        "item_count":        sum(len(r.get("items", [])) for r in receipts),
    })


@app.route("/api/process_pipeline", methods=["POST"])
def process_pipeline():
    files = request.files.getlist("receipts")
    if not files:
        return jsonify({"error": "Нет файлов"}), 400

    if not OCR_AVAILABLE or not PARSER_AVAILABLE:
        return jsonify({
            "error": "Парсер или OCR недоступен. "
                     "Проверьте что src/ocr.py, parser.py, categorizer.py загружены."
        }), 500

    _data_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []

    for f in files:
        if not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        content = f.read()
        target = _data_dir / f.filename
        if target.exists() and target.read_bytes() == content:
            saved_paths.append(target)
            continue
        if target.exists():
            fid = hashlib.md5(content).hexdigest()[:6]
            target = _data_dir / f"{Path(f.filename).stem}_{fid}{ext}"
        target.write_bytes(content)
        saved_paths.append(target)

    if not saved_paths:
        return jsonify({"error": "Нет поддерживаемых изображений (jpg/png/webp)"}), 400

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "status":       "pending",
            "step":         "init",
            "progress":     0,
            "current_file": "",
            "log":          [],
            "result":       None,
            "total_files":  len(saved_paths),
            "created_at":   time.time(),
        }

    thread = threading.Thread(
        target=_pipeline_worker,
        args=(job_id, saved_paths),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "job_id":      job_id,
        "total_files": len(saved_paths),
        "message":     f"Запущена обработка {len(saved_paths)} файлов",
    })


@app.route("/api/job/<job_id>")
def job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Задача не найдена"}), 404
    return jsonify(job)


@app.route("/api/stats", methods=["POST"])
def stats_api():
    data = request.get_json(force=True)
    receipts = data.get("receipts", [])
    manual = data.get("manual", {})
    by_cat = {}
    receipt_total = 0.0
    item_count = 0

    for r in receipts:
        receipt_total += r.get("total", 0)
        for it in r.get("items", []):
            cat = it.get("category", "other")
            by_cat[cat] = by_cat.get(cat, 0) + it.get("price", 0)
            item_count += 1

    manual_clean = {k: float(v) for k, v in manual.items() if v and float(v) > 0}
    manual_total = sum(manual_clean.values())

    return jsonify({
        "receipt_total":       round(receipt_total, 2),
        "manual_total":        round(manual_total, 2),
        "grand_total":         round(receipt_total + manual_total, 2),
        "item_count":          item_count,
        "receipt_count":       len(receipts),
        "receipt_by_category": {k: round(v, 2) for k, v in by_cat.items()},
        "manual":              manual_clean,
    })


@app.route("/api/status")
def api_status():
    n = len(list(_parsed_dir.glob("*.json"))) if _parsed_dir.exists() else 0
    return jsonify({
        "ocr_available":     OCR_AVAILABLE,
        "parser_available":  PARSER_AVAILABLE,
        "stats_available":   STATS_AVAILABLE,
        "parsed_count":      n,
        "stats_file_exists": _stats_file.exists(),
    })


if __name__ == "__main__":
    PORT = 5000
    n = len(list(_parsed_dir.glob("*.json"))) if _parsed_dir.exists() else 0

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print("=" * 62)
    print("  Receipt Analytics  —  Flask сервер")
    print(f"  OCR:    {'✓ easyocr' if OCR_AVAILABLE else '✗'} | "
          f"Парсер: {'✓' if PARSER_AVAILABLE else '✗'} | "
          f"Stats: {'✓' if STATS_AVAILABLE else '✗'}")
    print(f"  Данные: {n} чеков в processed/")
    print("-" * 62)
    print(f"На этом компьютере:  http://localhost:{PORT}")
    print(f"Для других в сети:   http://{local_ip}:{PORT}")
    print()
    print("  Скиньте вторую ссылку — откроется у всех,")
    print("  кто подключён к той же Wi-Fi / сети.")
    print("=" * 62)

    app.run(host='0.0.0.0', port=PORT, use_reloader=False)