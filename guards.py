"""ตัวป้องกันทรัพยากรของ pdf-tools: โควตาดิสก์ของไฟล์ชั่วคราว + งบ RAM ของงานแปลงรูป
ใช้: ใน app.py ท้ายไฟล์ (ก่อน if __name__ == "__main__") เพิ่ม
        import guards; guards.init(app, UPLOAD_FOLDER, OUTPUT_FOLDER, parse_pages)
env: PDF_DISK_LIMIT_MB (5000), PDF_CONVERT_MEM_MB (600), PDF_TMP_DIR (ไดเรกทอรี tmp ที่นับรวมในโควตา; ค่าเริ่มต้น /tmp)"""
import os, shutil, threading
from flask import jsonify, request
from pypdf import PdfReader

DISK_LIMIT = int(os.environ.get('PDF_DISK_LIMIT_MB', '5000')) * 1024 * 1024
CONVERT_MEM_BUDGET = int(os.environ.get('PDF_CONVERT_MEM_MB', '600')) * 1024 * 1024
TMP_DIR = os.environ.get('PDF_TMP_DIR', '/tmp')
_evict_lock = threading.Lock()


def _dir_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for n in files:
            try:
                total += os.lstat(os.path.join(root, n)).st_size
            except OSError:
                pass
    return total


def init(app, upload_folder, output_folder, parse_pages):
    work_dirs = [upload_folder, output_folder, TMP_DIR]

    def disk_used():
        return sum(_dir_bytes(d) for d in work_dirs)

    def evict_oldest(target):
        """ลบเซสชัน (ไฟล์/โฟลเดอร์ระดับบนสุดใน uploads/outputs) เก่าสุดก่อน จนใช้พื้นที่ <= target; ข้ามชื่อที่ขึ้นต้นด้วย '.'"""
        with _evict_lock:
            items = []
            for base in (upload_folder, output_folder):
                for n in os.listdir(base):
                    if n.startswith('.'):
                        continue
                    p = os.path.join(base, n)
                    try:
                        items.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
            for _mt, p in sorted(items):
                if disk_used() <= target:
                    break
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    def estimate_convert_bytes(files, form):
        """pdf2image โหลดทุกหน้าที่แปลงเข้า RAM พร้อมกัน: หน้า x พิกเซล x 3 ไบต์ x 1.5"""
        try:
            dpi = int(form.get('dpi', 150))
        except ValueError:
            dpi = 150
        if dpi not in (72, 96, 150, 200, 300):
            dpi = 150
        worst = 0
        for i, f in enumerate(files):
            if not f.filename:
                continue
            try:
                r = PdfReader(f.stream)
                total = len(r.pages)
                box = r.pages[0].mediabox
                w_in, h_in = float(box.width) / 72, float(box.height) / 72
                sel = parse_pages(form.get(f'pages_{i}', ''), total)
                n = total if sel is None else (sel[-1] - sel[0] + 1)   # app.py ส่ง first_page..last_page ให้ pdf2image
                worst = max(worst, int(n * (w_in * dpi) * (h_in * dpi) * 3 * 1.5))
            except Exception:
                pass   # อ่านไม่ได้: ปล่อยให้ app.py รายงาน error เอง
            finally:
                try:
                    f.stream.seek(0)   # สำคัญ: ไม่งั้น f.save() จะได้ไฟล์ว่าง
                except Exception:
                    pass
        return worst

    @app.before_request
    def resource_guard():
        if request.method != 'POST' or request.endpoint not in ('convert', 'merge', 'compress'):
            return None
        incoming = request.content_length or 0
        if disk_used() + 3 * incoming > DISK_LIMIT:
            evict_oldest(DISK_LIMIT // 2)
            if disk_used() + 3 * incoming > DISK_LIMIT:
                return jsonify({'error': 'ระบบกำลังใช้งานหนาแน่น พื้นที่ชั่วคราวเต็ม กรุณาลองใหม่ในอีกสักครู่'}), 503
        if request.endpoint == 'convert':
            need = estimate_convert_bytes(request.files.getlist('files'), request.form)
            if need > CONVERT_MEM_BUDGET:
                return jsonify({'error': f'งานนี้ใช้หน่วยความจำประมาณ {need >> 20} MB เกินที่กำหนด ({CONVERT_MEM_BUDGET >> 20} MB) '
                                         'กรุณาลดค่า DPI หรือเลือกแปลงเป็นช่วงหน้า (เช่น 1-20)'}), 413
        return None

    @app.after_request
    def disk_after(resp):
        # กันพื้นที่ล้นจากงานที่ผลลัพธ์ใหญ่กว่าที่ประเมิน (เช่น PNG หลายร้อยหน้า)
        try:
            if request.method == 'POST' and disk_used() > DISK_LIMIT:
                evict_oldest(int(DISK_LIMIT * 0.8))
        except Exception:
            pass
        return resp
