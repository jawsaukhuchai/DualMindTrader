#!/usr/bin/env bash
set -e

# เคลียร์ผลเก่าก่อน
coverage erase

# รัน pytest ครอบคลุมทุกไฟล์ในโฟลเดอร์ tests/
pytest \
  --maxfail=1 \
  --disable-warnings \
  --cov=mind2_python.decision_engine \
  --cov-report=term-missing \
  --cov-report=html \
  tests/

# สรุปผล
echo "=================================================="
echo "HTML coverage report สร้างไว้ที่: htmlcov/index.html"
echo "เปิดด้วย browser:  xdg-open htmlcov/index.html"
