# PDF → รูปภาพ (PDF to Image Converter)

## การติดตั้ง
1. ติดตั้ง **Poppler for Windows**  
   ดาวน์โหลด: https://github.com/oschwartz10612/poppler-windows/releases  
   แตกไฟล์แล้วเพิ่ม `bin\` ใน PATH ของ Windows

2. ดับเบิลคลิก `install.bat` เพื่อติดตั้ง Python packages

## การใช้งาน
- ดับเบิลคลิก `run.bat`  
- เบราว์เซอร์จะเปิด http://localhost:5000 อัตโนมัติ  
- ลากหรือเลือกไฟล์ PDF หลายไฟล์  
- เลือกรูปแบบ (PNG / JPG / WEBP) และ DPI  
- กดแปลง → ดาวน์โหลดแบบรายไฟล์หรือ ZIP ทั้งหมด

## โครงสร้างโฟลเดอร์
```
PDF/
├── app.py          ← Flask backend
├── requirements.txt
├── install.bat     ← ติดตั้ง packages
├── run.bat         ← เปิดโปรแกรม
├── templates/
│   └── index.html  ← หน้าเว็บ
├── uploads/        ← ไฟล์ชั่วคราว (ลบอัตโนมัติ)
└── outputs/        ← รูปภาพที่แปลงแล้ว
```
