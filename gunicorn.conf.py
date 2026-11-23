import os, shutil

bind = "0.0.0.0:5000"
workers = 2
timeout = 300   # ไฟล์ PDF ใหญ่ใช้เวลาแปลง/บีบอัดนาน


def on_starting(server):
    """ล้างไฟล์ค้างตอนสตาร์ท/รีสตาร์ท (volume ไม่หายเองเหมือน tmpfs)"""
    for d in ("/app/uploads", "/app/outputs", os.environ.get("PDF_TMP_DIR", "/tmp")):
        try:
            for n in os.listdir(d):
                p = os.path.join(d, n)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
        except OSError:
            pass
