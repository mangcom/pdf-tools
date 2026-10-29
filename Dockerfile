FROM python:3.13-slim

# poppler-utils ให้ pdf2image เรียก pdftoppm/pdfinfo ได้ (แทน poppler/ ที่ bundle มาสำหรับ Windows)
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/
COPY static/ static/

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p uploads outputs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)" || exit 1

# ตัว -w (workers) / --timeout ปรับได้ตามทรัพยากรเครื่อง; timeout ยาวหน่อยเพราะไฟล์ PDF ใหญ่ใช้เวลาแปลง/บีบอัดได้หลายวินาที
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]
