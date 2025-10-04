# benchmarks/test_latency.py
import time
import os
import json
import csv
from datetime import datetime
import subprocess
import pytest
from mind2_python.decision_engine import DecisionEngine
from mind2_python.schema import parse_feed

CONFIG_PATH = "mind2_python/config.symbols.yaml"
RESULT_DIR = "benchmarks/results"
RESULT_JSON = os.path.join(RESULT_DIR, "benchmark_results.json")
RESULT_CSV = os.path.join(RESULT_DIR, "benchmark_results.csv")


@pytest.fixture(scope="module")
def engine():
    # ลด log ระดับ CRITICAL เพื่อไม่ให้ log หน่วง
    import logging
    logging.getLogger("DecisionEngine").setLevel(logging.CRITICAL)
    return DecisionEngine(config_path=CONFIG_PATH)


def make_feed(symbol, bid, ask, spread, atr, adx):
    return {
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "filters": {},
        "timeframes": {"H1": {"atr": atr, "adx": adx}},
        "timestamp": "2025-01-01T00:00:00Z",
    }


def record_result(symbol: str, elapsed: float, ticks: int):
    """บันทึกผล benchmark ลง CSV/JSON"""
    os.makedirs(RESULT_DIR, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()

    # หา git commit ถ้ามี
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    except Exception:
        commit = "unknown"

    record = {
        "timestamp": timestamp,
        "symbol": symbol,
        "ticks": ticks,
        "elapsed_sec": round(elapsed, 3),
        "ticks_per_sec": round(ticks / elapsed, 3),
        "commit": commit,
    }

    # Append JSON log
    data = []
    if os.path.exists(RESULT_JSON):
        try:
            with open(RESULT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = []
    data.append(record)
    with open(RESULT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Append CSV
    write_header = not os.path.exists(RESULT_CSV)
    with open(RESULT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "symbol", "ticks", "elapsed_sec", "ticks_per_sec", "commit"],
        )
        if write_header:
            writer.writeheader()
        writer.writerow(record)

    print(f"✅ Benchmark saved → {RESULT_JSON} & {RESULT_CSV}")


@pytest.mark.benchmark
def test_benchmark_latency_btc(engine):
    """Benchmark: process 5000 BTCUSDc ticks -> must finish under 60s."""
    start = time.time()
    for i in range(5000):
        feed = make_feed("BTCUSDc", 50000 + (i % 50), 50001 + (i % 50), 1, atr=40.0, adx=30.0)
        entry = parse_feed([feed])[0]
        _ = engine.process(entry)
    elapsed = time.time() - start
    print(f"\nBTCUSDc 5000 ticks in {elapsed:.2f}s")
    record_result("BTCUSDc", elapsed, 5000)
    assert elapsed < 60.0


@pytest.mark.benchmark
def test_benchmark_latency_xau(engine):
    """Benchmark: process 5000 XAUUSDc ticks -> must finish under 120s."""
    start = time.time()
    for i in range(5000):
        feed = make_feed("XAUUSDc", 1900 + (i % 10), 1900.1 + (i % 10), 0.1, atr=1.2, adx=25.0)
        entry = parse_feed([feed])[0]
        _ = engine.process(entry)
    elapsed = time.time() - start
    print(f"\nXAUUSDc 5000 ticks in {elapsed:.2f}s")
    record_result("XAUUSDc", elapsed, 5000)
    assert elapsed < 120.0
