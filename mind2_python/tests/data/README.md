# Mock Feed Data

ไฟล์ `mind1_feed.json` ในโฟลเดอร์นี้เป็น **mock feed** สำหรับใช้ในการทดสอบ `schema.py` และ integration tests ของ **Mind2 (Python Bot)**

## จุดประสงค์
- ใช้แทนไฟล์จริง `mind1_mt5/output/mind1_feed.json` ที่มาจาก **Mind1 EA (MQL5)**
- ช่วยให้สามารถรัน `pytest` ได้แม้ยังไม่มี EA ทำงาน
- ทดสอบได้ว่า `parse_feed()` และ `TradeEntry` สามารถอ่าน field ต่าง ๆ ได้ครบ:
  - `symbol`, `bid`, `ask`, `spread`
  - `volume`, `tick_volume`
  - `indicators` (ema_fast, ema_slow, rsi, macd, atr, bos)
  - `filters` (spread, news, sideway)

## วิธีใช้งาน
- ถ้าไฟล์จริง `mind1_mt5/output/mind1_feed.json` มีอยู่ → test จะใช้ไฟล์จริงอัตโนมัติ
- ถ้าไฟล์จริงไม่มี → test จะ fallback มาใช้ไฟล์ mock นี้แทน

## หมายเหตุ
- Mock feed มีข้อมูลตัวอย่างของ **EURUSDc** และ **XAUUSDc**
- สามารถแก้ไข/ขยายข้อมูล mock เพิ่ม symbol อื่น ๆ ได้ตามต้องการ
- อย่าใช้ feed mock นี้ในการเทรดจริง — มีไว้เฉพาะสำหรับ unit/integration tests เท่านั้น
