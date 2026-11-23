FROM python:3.13-slim

# poppler-utils ให้ pdf2image เรียก pdftoppm/pdfinfo ได้ (แทน poppler/ ที่ bundle มาสำหรับ Windows)
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py guards.py gunicorn.conf.py .
COPY templates/ templates/
COPY static/ static/

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p uploads outputs \
    && chown -R appuser:appuser /app

USER appuser

# ไฟล์ชั่วคราวของ Werkzeug/Python tempfile และโควตาดิสก์ของแอป ต้องชี้ไปที่ /tmp
# ซึ่งถูก mount เป็น named volume บนดิสก์ (ดู docker-compose.yml) ไม่ใช่ tmpfs ที่กิน RAM
ENV TMPDIR=/tmp \
    PDF_TMP_DIR=/tmp

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)" || exit 1

# จำนวน worker / timeout ของ gunicorn ปรับได้ใน gunicorn.conf.py ตามทรัพยากรเครื่อง
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
