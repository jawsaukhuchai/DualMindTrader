import os
import zipfile
import datetime
from pathlib import Path

# 📂 Path ของ Common\Files (แก้ไขตามเครื่องคุณ)
COMMON_FILES = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "Common" / "Files"

# Prefix ของไฟล์ log ที่ EA เขียน
LOG_PREFIX = "mind1_log_"
LOG_EXT = ".txt"

def zip_and_remove(log_path: Path):
    """บีบอัดไฟล์ log แล้วลบต้นฉบับ"""
    if not log_path.exists():
        return

    zip_path = log_path.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(log_path, arcname=log_path.name)
    os.remove(log_path)
    print(f"📦 Archived {log_path.name} → {zip_path.name}")

def rotate_logs():
    today = datetime.date.today()
    for file in COMMON_FILES.glob(f"{LOG_PREFIX}*{LOG_EXT}"):
        # extract date string เช่น mind1_log_2025-09-16.txt
        try:
            date_str = file.stem.replace(LOG_PREFIX, "")
            file_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue  # skip ถ้าไม่ตรง format

        # ถ้าไม่ใช่วันนี้ → zip & remove
        if file_date < today:
            zip_and_remove(file)

if __name__ == "__main__":
    rotate_logs()
