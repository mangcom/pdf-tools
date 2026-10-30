# PDF Tools

เว็บแอป Flask สำหรับจัดการไฟล์ PDF แบบง่าย ๆ ผ่านเบราว์เซอร์ มี 3 เมนูหลัก:

| เมนู | ทำอะไร |
|---|---|
| 🖼️ **แปลง PDF → รูปภาพ** | แปลงแต่ละหน้าของ PDF เป็นไฟล์รูป (PNG / JPG / WEBP) เลือก DPI และเลือกช่วงหน้าได้ต่อไฟล์ รองรับหลายไฟล์พร้อมกัน ดาวน์โหลดทีละรูปหรือ ZIP รวด |
| 📋 **รวม PDF (Merge)** | รวมหลายไฟล์ PDF เป็นไฟล์เดียว ลากสลับลำดับไฟล์ก่อน-หลังได้ |
| 📦 **ลดขนาดไฟล์ PDF (Compress)** | บีบอัด PDF ให้ไม่เกินขนาดที่กำหนด (เช่น 4MB → ไม่เกิน 2MB) โดยลดคุณภาพ/ขนาดรูปภาพในไฟล์แบบไล่ระดับจนกว่าจะได้ขนาดตามต้องการ |

ไฟล์ที่อัปโหลดและไฟล์ที่สร้างขึ้น (รูปภาพ, ZIP, PDF ที่รวม/บีบอัดแล้ว) ทั้งหมดจะถูก **ลบอัตโนมัติภายใน 15 นาที** เพื่อไม่ให้เปลืองพื้นที่เซิร์ฟเวอร์ ผู้ใช้ต้องดาวน์โหลดให้ทันภายในเวลานี้

---

## สารบัญ

- [สถาปัตยกรรม / เทคโนโลยีที่ใช้](#สถาปัตยกรรม--เทคโนโลยีที่ใช้)
- [รันแบบ Docker (แนะนำสำหรับ Server จริง)](#รันแบบ-docker-แนะนำสำหรับ-server-จริง)
- [รันแบบ Local บน Windows (สำหรับพัฒนา)](#รันแบบ-local-บน-windows-สำหรับพัฒนา)
- [การตั้งค่า (Configuration)](#การตั้งค่า-configuration)
- [โครงสร้างโฟลเดอร์](#โครงสร้างโฟลเดอร์)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## สถาปัตยกรรม / เทคโนโลยีที่ใช้

- **Backend**: Flask (Python) + [pdf2image](https://github.com/Belval/pdf2image) (ครอบ Poppler) สำหรับแปลง PDF → รูป และ [pypdf](https://github.com/py-pdf/pypdf) สำหรับ merge/compress
- **Compress**: อ่านรูปภาพที่ฝังอยู่ในแต่ละหน้า PDF ด้วย pypdf → ย่อขนาด/ลดคุณภาพด้วย Pillow (JPEG re-encode) ไล่ระดับความบีบอัด 8 ระดับจนกว่าจะได้ขนาดไฟล์ตามเป้าหมาย (ใช้ได้ผลดีกับ PDF ที่เป็นรูปสแกน ถ้าเป็น PDF ข้อความ/เวกเตอร์ล้วนจะลดขนาดได้ไม่มาก เพราะไม่มีรูปภาพให้บีบอัด)
- **Production server**: Gunicorn (ไม่ใช้ Flask dev server ตอน deploy จริง)
- **Container**: Docker (`python:3.13-slim` + `poppler-utils`)
- **Frontend**: HTML/CSS/JavaScript ล้วน ไม่มี framework ไฟล์เดียวใน `templates/index.html`

---

## รันแบบ Docker (แนะนำสำหรับ Server จริง)

### สิ่งที่ต้องมี
- [Docker](https://docs.docker.com/get-docker/) และ Docker Compose (มีมาให้แล้วใน Docker Desktop / Docker Engine รุ่นใหม่)

### วิธีรัน

```bash
git clone https://github.com/mangcom/pdf-tools.git
cd pdf-tools
docker compose up -d --build
```

จากนั้นเข้าเว็บที่ `http://<server-ip>:5000`

ตรวจสอบสถานะ / health check:
```bash
docker compose ps
docker compose logs -f
```

หยุด / ปิด:
```bash
docker compose down
```

### รันด้วย `docker` ตรง ๆ (ไม่ใช้ compose)

```bash
docker build -t pdf-tools .
docker run -d --name pdf-tools -p 5000:5000 --restart unless-stopped pdf-tools
```

### สิ่งที่ Dockerfile ทำให้แล้ว
- ติดตั้ง `poppler-utils` (ใช้แทนโฟลเดอร์ `poppler/` ที่ bundle ไว้สำหรับ Windows เท่านั้น — โฟลเดอร์นั้นจะไม่ถูกก็อปปี้เข้า image)
- รันเป็น non-root user (`appuser`)
- รันด้วย Gunicorn ผ่าน `gunicorn.conf.py` (2 workers, timeout 300 วินาที — เผื่อไฟล์ PDF ใหญ่ที่ใช้เวลาแปลง/บีบอัดนาน; ล้างไฟล์ค้างใน `uploads/`, `outputs/`, `$PDF_TMP_DIR` ทุกครั้งที่ container เริ่ม/รีสตาร์ท)
- มี `HEALTHCHECK` ให้ตรวจสุขภาพ container อัตโนมัติ
- ไฟล์ชั่วคราวทั้งหมด (`uploads/`, `outputs/`, `/tmp`) เก็บบนดิสก์ผ่าน named volume ไม่ใช่ RAM/tmpfs — ดู [ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์](#ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์)

### นำไปใช้งานหลัง Reverse Proxy (nginx / Caddy / Traefik)

แอปรองรับไฟล์อัปโหลดสูงสุด **200MB ต่อ request** (`MAX_CONTENT_LENGTH` ใน `app.py`) ถ้าวาง reverse proxy ไว้หน้า container อย่าลืมปรับค่าที่ฝั่ง proxy ให้สอดคล้องกัน ไม่เช่นนั้นไฟล์ใหญ่จะถูกปฏิเสธก่อนถึงแอป

ตัวอย่าง nginx:
```nginx
server {
    listen 80;
    server_name pdf.example.com;

    client_max_body_size 200M;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 300s;   # ให้สอดคล้องกับ gunicorn --timeout
    }
}
```

ควรทำ HTTPS (เช่นผ่าน Let's Encrypt / Certbot หรือ Caddy ที่จัดการ TLS ให้อัตโนมัติ) ก่อนเปิดใช้งานจริงบนอินเทอร์เน็ต เพราะไฟล์ PDF ที่อัปโหลดอาจมีข้อมูลสำคัญ

### ข้อมูลไม่ถูกเก็บถาวร

`docker-compose.yml` สร้าง named volume `uploads` และ `outputs` ไว้ให้ แต่เนื่องจากแอปลบไฟล์อัตโนมัติภายใน 15 นาทีอยู่แล้ว (ดู [การตั้งค่า](#การตั้งค่า-configuration)) จึงไม่จำเป็นต้อง backup volume เหล่านี้

### ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์

ไฟล์ชั่วคราวทั้งหมด (`uploads/`, `outputs/`, และไฟล์พักของ Werkzeug ที่ `/tmp`) เก็บบนดิสก์ผ่าน Docker **named volume** (`uploads`, `outputs`, `work-tmp`) ไม่ใช่ RAM/tmpfs — ใช้ชื่อ volume แบบนี้เพื่อให้ `docker-compose.yml` ไฟล์เดียวรันได้ทั้ง Docker Desktop บน Windows และ Docker บน Linux โดยไม่ต้องพึ่ง path เฉพาะระบบปฏิบัติการ (เช่น `/srv/...`)

ความแตกต่างระหว่างสองแพลตฟอร์มที่ควรรู้:
- **Linux**: named volume อยู่ใต้ `/var/lib/docker/volumes/...` ซึ่งใช้ดิสก์จริงของโฮสต์ ถ้าต้องการ**เพดานแข็ง** (hard limit) ของพื้นที่ดิสก์ แนะนำให้เตรียม partition/ดิสก์ขนาดคงที่แยกไว้ แล้วใช้ **bind mount** ไปที่ path นั้นแทน named volume (ปรับ `volumes:` ใน `docker-compose.yml` เอง)
- **Docker Desktop (Windows)**: named volume อยู่ในดิสก์เสมือนของ WSL2 ซึ่งไม่มีเพดานแข็งตามขนาดไฟล์ volume (ขยายได้จนกว่าดิสก์ WSL2/โฮสต์จะเต็ม) จึงต้องพึ่ง**โควตาระดับแอป** (`PDF_DISK_LIMIT_MB`) เป็นตัวกันหลักแทน

โควตาระดับแอปและตัวกัน RAM ของงานแปลงรูปอยู่ใน `guards.py` (ลงทะเบียน `before_request`/`after_request` เพียงบรรทัดเดียวใน `app.py`):
- ก่อนรับ `POST /convert`, `/merge`, `/compress`: ถ้าพื้นที่ที่ใช้ไปแล้ว + ไฟล์ที่กำลังอัปโหลด (ประมาณ 3 เท่าของ `Content-Length`) เกิน `PDF_DISK_LIMIT_MB` จะลบเซสชันเก่าสุดก่อน ถ้ายังไม่พอจะตอบ `503`
- หลังงานเสร็จ ถ้าพื้นที่ที่ใช้ยังเกินโควตา จะลบเซสชันเก่าสุดจนเหลือ 80% ของโควตา
- ก่อน `/convert`: ประมาณ RAM ที่ `pdf2image` ต้องใช้ (หน้าที่เลือกแปลง × ขนาดพิกเซลตาม DPI × 3 ไบต์ × 1.5) จาก `pypdf` ถ้าเกิน `PDF_CONVERT_MEM_MB` จะตอบ `413` พร้อมคำแนะนำให้ลด DPI หรือเลือกช่วงหน้า — ป้องกันกรณี PDF หลายร้อยหน้าที่ DPI สูงซึ่งโหลดทุกหน้าเข้า RAM พร้อมกัน
- ไฟล์/โฟลเดอร์ที่ขึ้นต้นด้วย `.` (เช่น `.last_cleanup`) จะไม่ถูกลบโดยตัวกันโควตา

---

## รันแบบ Local บน Windows (สำหรับพัฒนา)

### 1. ติดตั้ง Poppler for Windows

ดาวน์โหลดจาก: https://github.com/oschwartz10612/poppler-windows/releases

แตกไฟล์ ZIP แล้ว**คัดลอกโฟลเดอร์ `poppler-xx.xx.x\` ทั้งหมดไปวางไว้ที่ root ของโปรเจกต์ แล้วเปลี่ยนชื่อเป็น `poppler/`** ให้ได้โครงสร้างแบบนี้:

```
PDF/
└── poppler/
    └── Library/
        └── bin/
            ├── pdftoppm.exe
            ├── pdfinfo.exe
            └── ...
```

(ไม่ต้องไปเพิ่ม PATH ของ Windows เอง เพราะ `run.bat` จะตั้ง PATH ชี้ไปที่โฟลเดอร์นี้ให้อัตโนมัติ)

> โฟลเดอร์ `poppler/` ไม่ได้อยู่ใน git repo (ถูก ignore ไว้ใน `.gitignore`) เพราะเป็นไบนารีเฉพาะ Windows — ต้องดาวน์โหลดเองตามขั้นตอนนี้

### 2. ติดตั้ง Python packages

ดับเบิลคลิก **`install.bat`** (จะสร้าง virtualenv `venv/` และ `pip install -r requirements.txt` ให้อัตโนมัติ)

หรือสั่งเองผ่าน terminal:
```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

### 3. รันแอป

ดับเบิลคลิก **`run.bat`** หรือสั่ง:
```powershell
venv\Scripts\python app.py
```

เบราว์เซอร์จะเปิด `http://localhost:5000` ให้อัตโนมัติ (จาก `run.bat`)

> โหมดนี้รัน Flask dev server (debug=True โดย default) — เหมาะสำหรับพัฒนา/ทดสอบเท่านั้น สำหรับ production ให้ใช้ Docker ตามหัวข้อด้านบน

---

## การตั้งค่า (Configuration)

ค่าเหล่านี้กำหนดไว้ในส่วนบนของ `app.py` ปรับได้โดยตรงถ้าต้องการ (ยังไม่ได้ทำเป็น environment variable):

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `MAX_CONTENT_LENGTH` | `200 * 1024 * 1024` (200MB) | ขนาดรวมสูงสุดของไฟล์ที่อัปโหลดต่อ 1 request |
| `SESSION_TTL` | `15 * 60` (15 นาที) | อายุไฟล์สูงสุดก่อนถูกลบอัตโนมัติ ใช้กับทั้ง 3 เมนู ทั้งไฟล์ต้นฉบับที่ตกค้างใน `uploads/` และไฟล์ที่สร้างใหม่ใน `outputs/` |
| ช่วงเวลาตรวจสอบ cleanup | ทุก 1 นาที | เช็คทุกครั้งที่มี request เข้ามา (ผ่าน `.last_cleanup` marker) ว่าถึงเวลาต้องกวาดไฟล์เก่าหรือยัง |

ค่าที่ปรับผ่าน environment variable ได้ (เวลารันแบบ `python app.py` โดยตรง ไม่เกี่ยวกับตอนรันด้วย Gunicorn):

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `FLASK_DEBUG` | `1` | ตั้งเป็น `0` เพื่อปิด Flask debug mode |

ค่าที่ปรับผ่าน environment variable ได้ทั้งตอนรันแบบ local และผ่าน Docker (`guards.py`, ดู [ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์](#ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์)) — ตั้งไว้แล้วใน `docker-compose.yml`, ไม่ต้องตั้งเพิ่มเองเพื่อให้ `docker compose up -d --build` รันได้ทันที:

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `PDF_DISK_LIMIT_MB` | `5000` (ตั้งเป็น `4300` ใน `docker-compose.yml`) | โควตาดิสก์รวมของ `uploads/` + `outputs/` + `$PDF_TMP_DIR` (MB) เกินนี้จะลบเซสชันเก่าสุดก่อน หรือตอบ `503` ถ้าลบแล้วยังไม่พอ |
| `PDF_CONVERT_MEM_MB` | `600` | งบ RAM โดยประมาณต่องาน `/convert` หนึ่งครั้ง (MB) เกินนี้ตอบ `413` |
| `PDF_TMP_DIR` | `/tmp` | ไดเรกทอรีที่ Werkzeug/Python ใช้พักไฟล์อัปโหลดขนาดใหญ่ และนับรวมในโควตาดิสก์ด้านบน ต้องชี้ไปที่ดิสก์จริง (ดูหัวข้อด้านบน) ไม่ใช่ tmpfs |

ปรับจำนวน worker / timeout ของ Gunicorn ได้ที่ `gunicorn.conf.py`:
```python
workers = 2
timeout = 300
```
กฎทั่วไป: ตั้ง `workers` ประมาณ `(จำนวน CPU core x 2) + 1` และเพิ่ม `timeout` ถ้าเซิร์ฟเวอร์ต้องรับไฟล์ PDF ขนาดใหญ่/จำนวนหน้ามาก ๆ บ่อย ๆ

---

## โครงสร้างโฟลเดอร์

```
PDF/
├── app.py               ← Flask backend (routes, logic แปลง/รวม/บีบอัด PDF, cleanup)
├── guards.py            ← โควตาดิสก์ของไฟล์ชั่วคราว + งบ RAM ของงานแปลงรูป (before_request/after_request)
├── gunicorn.conf.py     ← ค่า config ของ Gunicorn + ล้างไฟล์ค้างตอน container เริ่ม/รีสตาร์ท
├── requirements.txt     ← Python dependencies
├── Dockerfile           ← สร้าง image สำหรับ production (ใช้ poppler-utils + gunicorn)
├── docker-compose.yml   ← รัน container พร้อม named volume สำหรับ uploads/outputs/tmp (ดิสก์ ไม่ใช่ RAM)
├── .dockerignore
├── install.bat          ← (Windows) สร้าง venv + ติดตั้ง packages
├── run.bat              ← (Windows) รันแอปแบบ local พร้อมตั้ง PATH ของ poppler
├── templates/
│   └── index.html       ← หน้าเว็บทั้งหมด (3 แท็บ: แปลง / รวม / บีบอัด)
├── static/              ← (สำรองไว้สำหรับ static asset เพิ่มเติม ปัจจุบันยังไม่ใช้)
├── poppler/              ← (ไม่อยู่ใน git) Poppler for Windows binary สำหรับรัน local
├── uploads/              ← ไฟล์ที่อัปโหลดชั่วคราว ลบอัตโนมัติ (ไม่อยู่ใน git)
└── outputs/              ← ไฟล์ผลลัพธ์ (รูป/ZIP/PDF) ลบอัตโนมัติ (ไม่อยู่ใน git)
```

---

## API Reference

ทุก endpoint ที่รับไฟล์ใช้ `multipart/form-data` field ชื่อ `files` (รับได้หลายไฟล์)

| Method | Path | คำอธิบาย |
|---|---|---|
| `GET` | `/` | หน้าเว็บหลัก |
| `POST` | `/convert` | แปลง PDF → รูปภาพ. form fields: `files`, `format` (`PNG`/`JPG`/`WEBP`), `dpi` (`72/96/150/200/300`), `pages_<i>` (ช่วงหน้าของไฟล์ที่ i เช่น `1,3-5,8`, เว้นว่าง = ทุกหน้า) |
| `GET` | `/img/<sid>/<filename>` | ดาวน์โหลดรูปที่แปลงแล้วทีละไฟล์ |
| `GET` | `/zip/<sid>` | ดาวน์โหลดรูปทั้ง session เป็น ZIP |
| `POST` | `/merge` | รวม PDF หลายไฟล์. form fields: `files`, `order` (JSON array ของ index ลำดับไฟล์ เช่น `[2,0,1]`) |
| `GET` | `/merged/<sid>` | ดาวน์โหลดไฟล์ PDF ที่รวมแล้ว |
| `POST` | `/compress` | บีบอัด PDF. form fields: `files`, `target_mb` (ขนาดไฟล์สูงสุดที่ต้องการ หน่วย MB เช่น `2`) |
| `GET` | `/compressed/<sid>/<filename>` | ดาวน์โหลด PDF ที่บีบอัดแล้วทีละไฟล์ |
| `GET` | `/compress-zip/<sid>` | ดาวน์โหลด PDF ที่บีบอัดแล้วทั้ง session เป็น ZIP |

ทุก response (ยกเว้นหน้าเว็บและดาวน์โหลดไฟล์) เป็น JSON มีโครงสร้างคร่าว ๆ ว่า `{ "sid": "...", "results": [...], "errors": [...] }`

---

## Troubleshooting

**`/convert` หรือ `/compress` error บอกหา poppler/pdftoppm ไม่เจอ**
- รัน local บน Windows: ตรวจว่ามีโฟลเดอร์ `poppler/Library/bin/pdftoppm.exe` อยู่จริง และรันผ่าน `run.bat` (ไม่ใช่รัน `python app.py` ตรง ๆ โดยไม่ตั้ง PATH)
- รันผ่าน Docker: ไม่ควรเกิดปัญหานี้เพราะ `poppler-utils` ถูกติดตั้งผ่าน `apt-get` ให้แล้วใน image ถ้ายัง error ให้ build image ใหม่ (`docker compose build --no-cache`)

**อัปโหลดไฟล์ใหญ่แล้วได้ error 413 (Request Entity Too Large)**
- ไฟล์รวมเกิน 200MB ต่อ request (ดู `MAX_CONTENT_LENGTH`) หรือถ้ามี reverse proxy อยู่หน้าแอป ให้เช็ค `client_max_body_size` (nginx) หรือ config เทียบเท่าของ proxy ที่ใช้ด้วย

**บีบอัด PDF (Compress) แล้วขนาดไม่ลดลงเลยหรือลดได้ไม่มาก**
- ถ้า PDF เป็นข้อความ/เวกเตอร์ล้วน (ไม่มีรูปภาพฝังอยู่) ระบบจะบีบอัดได้แค่ระดับ content stream เท่านั้น ลดขนาดได้ไม่มาก เพราะกลไกการบีบอัดเน้นลดคุณภาพ/ขนาดรูปภาพที่ฝังในไฟล์เป็นหลัก (ใช้ได้ผลดีกับไฟล์สแกน/รูปถ่าย)

**ดาวน์โหลดไฟล์ไม่ทัน ไฟล์หายไปแล้ว**
- ไฟล์ทุกเมนูถูกลบอัตโนมัติภายใน 15 นาทีนับจากตอนสร้าง (ดู `SESSION_TTL`) ต้องประมวลผลใหม่อีกครั้งถ้าพลาดเวลา

**แปลง PDF เป็นรูปแล้วได้ error 413 "งานนี้ใช้หน่วยความจำประมาณ ... MB เกินที่กำหนด"**
- PDF หน้ามาก + DPI สูงใช้ RAM ในการแปลงมากเกินงบ `PDF_CONVERT_MEM_MB` (ค่าเริ่มต้น 600) ให้ลด DPI หรือเลือกแปลงเฉพาะบางช่วงหน้าแทนทั้งไฟล์ (ดู [ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์](#ที่เก็บไฟล์ชั่วคราวและโควตาดิสก์))

**ได้ error 503 "ระบบกำลังใช้งานหนาแน่น พื้นที่ชั่วคราวเต็ม"**
- พื้นที่ดิสก์ของ `uploads/`, `outputs/`, `$PDF_TMP_DIR` รวมกันเกิน `PDF_DISK_LIMIT_MB` และลบเซสชันเก่าสุดแล้วก็ยังไม่พอ (มักเกิดเมื่อมีผู้ใช้หลายคนอัปโหลดไฟล์ใหญ่พร้อมกัน) ลองใหม่อีกครั้งในอีกสักครู่ หรือเพิ่มค่า `PDF_DISK_LIMIT_MB` ถ้าดิสก์ของเครื่องมีพื้นที่เหลือจริง
