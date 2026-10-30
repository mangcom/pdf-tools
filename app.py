import os
import uuid
import shutil
import threading
import time
import zipfile
import io
from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path, pdfinfo_from_path
from pypdf import PdfWriter, PdfReader
from PIL import Image

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "outputs")
SESSION_TTL   = 15 * 60    # 15 นาที — ไฟล์ทุกเมนู (ต้นฉบับ + ไฟล์ที่สร้างใหม่) จะถูกลบหลังจากนี้

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ─────────────────────────── helpers ──────────────────────────────

def allowed_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


def parse_pages(page_str, total_pages):
    """'1,3-5,8' -> sorted 1-based list  |  None = ทุกหน้า"""
    s = page_str.strip()
    if not s or s.lower() == "all":
        return None
    pages = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            try:
                lo, hi = int(a.strip()), int(b.strip())
            except ValueError:
                raise ValueError(f'ช่วงหน้าไม่ถูกต้อง: "{part}"')
            if lo < 1 or hi < lo:
                raise ValueError(f'ช่วงหน้าไม่ถูกต้อง: "{part}"')
            pages.update(p for p in range(lo, hi + 1) if p <= total_pages)
        else:
            try:
                p = int(part)
            except ValueError:
                raise ValueError(f'หมายเลขหน้าไม่ถูกต้อง: "{part}"')
            if 1 <= p <= total_pages:
                pages.add(p)
    if not pages:
        raise ValueError("ไม่มีหน้าที่ถูกต้องในช่วงของไฟล์นี้")
    return sorted(pages)


def _sweep_folder(folder, now, marker=None):
    for name in os.listdir(folder):
        path = os.path.join(folder, name)
        if marker is not None and path == marker:
            continue
        try:
            if os.path.getmtime(path) < now - SESSION_TTL:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                elif os.path.isfile(path):
                    os.remove(path)
        except Exception:
            pass


def cleanup_old_sessions():
    """ลบไฟล์/โฟลเดอร์ที่เก่ากว่า SESSION_TTL ทั้งใน uploads (ต้นฉบับที่ตกค้าง)
    และ outputs (ไฟล์ที่สร้างใหม่ทุกเมนู: แปลงรูป/zip, merge, compress)"""
    now = time.time()
    marker = os.path.join(OUTPUT_FOLDER, ".last_cleanup")
    _sweep_folder(UPLOAD_FOLDER, now)
    _sweep_folder(OUTPUT_FOLDER, now, marker=marker)


@app.before_request
def _periodic_cleanup():
    """ทำความสะอาดทุก ๆ ครั้งที่มี request (lightweight check)"""
    # ไม่ให้รันบ่อยเกินไป — เช็คทุก 1 นาที เพื่อให้ไฟล์ถูกลบใกล้เคียง 15 นาทีจริง
    marker = os.path.join(OUTPUT_FOLDER, ".last_cleanup")
    now = time.time()
    try:
        if os.path.exists(marker) and now - os.path.getmtime(marker) < 60:
            return
        open(marker, "w").close()
        threading.Thread(target=cleanup_old_sessions, daemon=True).start()
    except Exception:
        pass


# ─────────────────────────── compress helpers ──────────────────────

# เรียงจากบีบอัดน้อย -> บีบอัดมาก (quality ของ JPEG, ความกว้าง/สูงสูงสุดของรูป)
COMPRESSION_PRESETS = [
    (90, 2200),
    (85, 2000),
    (75, 1800),
    (65, 1600),
    (55, 1400),
    (45, 1200),
    (35, 1000),
    (25, 800),
]


def compress_pdf_bytes(input_path, quality, max_dim):
    """บีบอัด PDF หนึ่งรอบ (ลดคุณภาพ/ขนาดรูปภาพ + compress content stream) คืนค่าเป็น bytes"""
    reader = PdfReader(input_path)
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        try:
            page.compress_content_streams(level=9)
        except Exception:
            pass
        try:
            images = list(page.images)
        except Exception:
            images = []
        for img in images:
            try:
                pil = img.image
                if pil.mode in ("RGBA", "P", "LA"):
                    pil = pil.convert("RGB")
                w, h = pil.size
                if max(w, h) > max_dim:
                    scale = max_dim / max(w, h)
                    pil = pil.resize(
                        (max(1, int(w * scale)), max(1, int(h * scale))),
                        Image.LANCZOS,
                    )
                img.replace(pil, quality=quality)
            except Exception:
                pass
    try:
        writer.compress_identical_objects()
    except Exception:
        pass
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def compress_pdf_to_target(input_path, target_bytes):
    """ไล่ลดคุณภาพทีละระดับจนกว่าขนาดไฟล์ <= target_bytes
    คืนค่า (bytes, final_size, reached_target)"""
    orig_size = os.path.getsize(input_path)
    if orig_size <= target_bytes:
        with open(input_path, "rb") as fp:
            return fp.read(), orig_size, True

    best_bytes, best_size = None, None
    for quality, max_dim in COMPRESSION_PRESETS:
        data = compress_pdf_bytes(input_path, quality, max_dim)
        size = len(data)
        if best_size is None or size < best_size:
            best_bytes, best_size = data, size
        if size <= target_bytes:
            return data, size, True
    return best_bytes, best_size, False


# ─────────────────────────── routes ───────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── CONVERT PDF → IMAGES ──────────────────────────────────────────

@app.route("/convert", methods=["POST"])
def convert():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "กรุณาเลือกไฟล์ PDF"}), 400

    fmt  = request.form.get("format", "PNG").upper()
    dpi  = int(request.form.get("dpi", 150))
    if dpi not in [72, 96, 150, 200, 300]:
        dpi = 150
    pages_list = [request.form.get(f"pages_{i}", "").strip()
                  for i in range(len(files))]

    sid         = str(uuid.uuid4())[:8]
    session_out = os.path.join(OUTPUT_FOLDER, sid)
    os.makedirs(session_out, exist_ok=True)

    results, errors = [], []

    for idx, f in enumerate(files):
        if f.filename == "" or not allowed_pdf(f.filename):
            errors.append(f"{f.filename}: ไม่ใช่ไฟล์ PDF")
            continue
        orig  = secure_filename(f.filename)
        bname = os.path.splitext(orig)[0]
        pdf_p = os.path.join(UPLOAD_FOLDER, f"{sid}_{orig}")
        f.save(pdf_p)
        try:
            info   = pdfinfo_from_path(pdf_p)
            total  = info["Pages"]
            sel    = parse_pages(pages_list[idx] if idx < len(pages_list) else "", total)

            if sel is None:
                imgs   = convert_from_path(pdf_p, dpi=dpi)
                pnums  = list(range(1, len(imgs) + 1))
            else:
                lo, hi = sel[0], sel[-1]
                imgs   = convert_from_path(pdf_p, dpi=dpi, first_page=lo, last_page=hi)
                keep   = set(sel)
                pairs  = [(lo + i, im) for i, im in enumerate(imgs) if (lo + i) in keep]
                pnums  = [p for p, _ in pairs]
                imgs   = [im for _, im in pairs]

            ext = "jpg" if fmt == "JPG" else fmt.lower()
            file_images = []
            for pn, page in zip(pnums, imgs):
                name = f"{bname}_p{pn:03d}.{ext}"
                path = os.path.join(session_out, name)
                page.save(path, "JPEG" if fmt == "JPG" else fmt, quality=90)
                file_images.append({
                    "name": name,
                    "url":  url_for("dl_image", sid=sid, filename=name)
                })
            results.append({"pdf": orig, "total": total,
                            "converted": len(file_images), "images": file_images})
        except ValueError as ve:
            errors.append(f"{f.filename}: {ve}")
        except Exception as e:
            errors.append(f"{f.filename}: {e}")
        finally:
            if os.path.exists(pdf_p):
                os.remove(pdf_p)

    if not results and errors:
        return jsonify({"error": "; ".join(errors)}), 500
    return jsonify({"sid": sid, "results": results, "errors": errors})


@app.route("/img/<sid>/<filename>")
def dl_image(sid, filename):
    path = os.path.join(OUTPUT_FOLDER, secure_filename(sid), secure_filename(filename))
    if not os.path.exists(path):
        return "ไม่พบไฟล์", 404
    return send_file(path, as_attachment=True)


@app.route("/zip/<sid>")
def dl_zip(sid):
    safe        = secure_filename(sid)
    session_out = os.path.join(OUTPUT_FOLDER, safe)
    if not os.path.isdir(session_out):
        return "ไม่พบไฟล์", 404
    zip_path = os.path.join(OUTPUT_FOLDER, f"{safe}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in sorted(os.listdir(session_out)):
            zf.write(os.path.join(session_out, fn), fn)
    return send_file(zip_path, as_attachment=True,
                     download_name="converted_images.zip")


# ── MERGE PDFs ────────────────────────────────────────────────────

@app.route("/merge", methods=["POST"])
def merge():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "กรุณาเลือกไฟล์ PDF อย่างน้อย 2 ไฟล์"}), 400

    # รับลำดับไฟล์จาก client (index ใน files[])
    import json
    order_raw = request.form.get("order", "")
    try:
        order = json.loads(order_raw) if order_raw else list(range(len(files)))
    except Exception:
        order = list(range(len(files)))

    sid      = str(uuid.uuid4())[:8]
    merge_dir = os.path.join(OUTPUT_FOLDER, f"merge_{sid}")
    os.makedirs(merge_dir, exist_ok=True)

    saved = []
    errors = []
    for i, f in enumerate(files):
        if f.filename == "" or not allowed_pdf(f.filename):
            errors.append(f"{f.filename}: ไม่ใช่ไฟล์ PDF")
            continue
        orig  = secure_filename(f.filename)
        path  = os.path.join(UPLOAD_FOLDER, f"{sid}_{i}_{orig}")
        f.save(path)
        saved.append({"idx": i, "orig": orig, "path": path})

    if len(saved) < 1:
        return jsonify({"error": "ไม่มีไฟล์ PDF ที่ถูกต้อง"}), 400

    # เรียงตาม order
    idx_map = {s["idx"]: s for s in saved}
    ordered = [idx_map[i] for i in order if i in idx_map]
    if not ordered:
        ordered = saved

    out_name = "merged.pdf"
    out_path = os.path.join(merge_dir, out_name)
    writer   = PdfWriter()
    file_list = []
    try:
        for s in ordered:
            reader = PdfReader(s["path"])
            for page in reader.pages:
                writer.add_page(page)
            file_list.append(s["orig"])
        with open(out_path, "wb") as fp:
            writer.write(fp)
    except Exception as e:
        return jsonify({"error": f"รวม PDF ไม่สำเร็จ: {e}"}), 500
    finally:
        for s in saved:
            if os.path.exists(s["path"]):
                os.remove(s["path"])

    total_pages = sum(1 for _ in PdfReader(out_path).pages)
    return jsonify({
        "sid":         sid,
        "url":         url_for("dl_merged", sid=sid),
        "files":       file_list,
        "total_pages": total_pages,
        "errors":      errors,
    })


@app.route("/merged/<sid>")
def dl_merged(sid):
    safe = secure_filename(sid)
    path = os.path.join(OUTPUT_FOLDER, f"merge_{safe}", "merged.pdf")
    if not os.path.exists(path):
        return "ไม่พบไฟล์", 404
    return send_file(path, as_attachment=True,
                     download_name="merged.pdf")


# ── COMPRESS PDF ──────────────────────────────────────────────────

@app.route("/compress", methods=["POST"])
def compress():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "กรุณาเลือกไฟล์ PDF"}), 400

    try:
        target_mb = float(request.form.get("target_mb", 2))
    except ValueError:
        target_mb = 2.0
    target_mb = max(0.1, min(target_mb, 500))
    target_bytes = int(target_mb * 1024 * 1024)

    sid         = str(uuid.uuid4())[:8]
    session_out = os.path.join(OUTPUT_FOLDER, f"compress_{sid}")
    os.makedirs(session_out, exist_ok=True)

    results, errors = [], []

    for f in files:
        if f.filename == "" or not allowed_pdf(f.filename):
            errors.append(f"{f.filename}: ไม่ใช่ไฟล์ PDF")
            continue
        orig  = secure_filename(f.filename)
        bname = os.path.splitext(orig)[0]
        pdf_p = os.path.join(UPLOAD_FOLDER, f"{sid}_{orig}")
        f.save(pdf_p)
        try:
            orig_size = os.path.getsize(pdf_p)
            data, final_size, reached = compress_pdf_to_target(pdf_p, target_bytes)
            out_name = f"{bname}_compressed.pdf"
            out_path = os.path.join(session_out, out_name)
            with open(out_path, "wb") as fp:
                fp.write(data)
            reduced_pct = round((1 - final_size / orig_size) * 100, 1) if orig_size else 0
            results.append({
                "name":           orig,
                "orig_size":      orig_size,
                "final_size":     final_size,
                "reduced_pct":    reduced_pct,
                "reached_target": reached,
                "url":            url_for("dl_compressed", sid=sid, filename=out_name),
            })
        except Exception as e:
            errors.append(f"{f.filename}: {e}")
        finally:
            if os.path.exists(pdf_p):
                os.remove(pdf_p)

    if not results and errors:
        return jsonify({"error": "; ".join(errors)}), 500
    return jsonify({"sid": sid, "target_mb": target_mb, "results": results, "errors": errors})


@app.route("/compressed/<sid>/<filename>")
def dl_compressed(sid, filename):
    path = os.path.join(OUTPUT_FOLDER, f"compress_{secure_filename(sid)}", secure_filename(filename))
    if not os.path.exists(path):
        return "ไม่พบไฟล์", 404
    return send_file(path, as_attachment=True)


@app.route("/compress-zip/<sid>")
def dl_compress_zip(sid):
    safe        = secure_filename(sid)
    session_out = os.path.join(OUTPUT_FOLDER, f"compress_{safe}")
    if not os.path.isdir(session_out):
        return "ไม่พบไฟล์", 404
    zip_path = os.path.join(OUTPUT_FOLDER, f"compress_{safe}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fn in sorted(os.listdir(session_out)):
            zf.write(os.path.join(session_out, fn), fn)
    return send_file(zip_path, as_attachment=True,
                     download_name="compressed_pdfs.zip")


import guards; guards.init(app, UPLOAD_FOLDER, OUTPUT_FOLDER, parse_pages)


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
