# Mind1 - EA MT5 (Indicators + Filters Provider)

## Overview
Mind1 เป็น EA ที่ทำหน้าที่เก็บ Indicators และตรวจ Risk Filters
แล้วส่งออกผลลัพธ์เป็น JSON → ใช้โดย Mind2 (Python Bot)

## Files
- `Mind1_EA.mq5` : EA หลัก
- `config_mt5.ini` : ค่า config เช่น spread_limit, filters
- `output/mind1_feed.json` : JSON ที่ export ออกมา

## Output JSON Structure
```json
[
  {
    "symbol": "EURUSDc",
    "timeframe": "M5",
    "timestamp": "2025-09-16T12:00:00Z",
    "indicators": {
      "ema_fast": 1.1762,
      "ema_slow": 1.1758,
      "rsi": 47.5,
      "macd_main": -0.0003,
      "macd_signal": -0.0001,
      "atr": 0.0012,
      "bos": "bearish"
    },
    "filters": {
      "spread": {"value": 12.0, "limit": 25, "pass": true},
      "news": {"impact": "NONE", "pass": true},
      "sideway": {"state": false, "pass": true}
    }
  }
]
