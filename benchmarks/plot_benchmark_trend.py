"""
📊 DualMindTrader Benchmark Trend Plotter
เวอร์ชันอัปเดตสำหรับ Plotly ≥ 6.3 (รองรับ Kaleido + Chrome)
อ่านผล benchmark จาก benchmarks/results/benchmark_results.csv
และวาดกราฟ performance trend (ticks/sec ต่อ timestamp)
"""

import os
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime

# ==== PATH CONFIG ====
RESULT_CSV = "benchmarks/results/benchmark_results.csv"
OUTPUT_HTML = "benchmarks/results/benchmark_trend.html"
OUTPUT_PNG = "benchmarks/results/benchmark_trend.png"

# ==== PERFORMANCE BASELINES ====
BASELINES = {
    "BTCUSDc": 100,  # expected min ticks/sec
    "XAUUSDc": 50,
}


# ------------------------------------------------------
def load_benchmark_data(path: str) -> pd.DataFrame:
    """โหลดข้อมูล benchmark จาก CSV"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ ไม่พบไฟล์ benchmark CSV: {path}")
    df = pd.read_csv(path)
    if "timestamp" not in df or "symbol" not in df:
        raise ValueError("❌ CSV ไม่มีคอลัมน์ที่จำเป็น (timestamp, symbol)")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    return df


# ------------------------------------------------------
def plot_trend(df: pd.DataFrame):
    """สร้างกราฟ performance trend และบันทึกผล"""
    print("📈 กำลังวาดกราฟ performance trend ...")

    # กราฟหลัก (interactive)
    fig = px.line(
        df,
        x="timestamp",
        y="ticks_per_sec",
        color="symbol",
        markers=True,
        title="DualMindTrader Performance Trend (ticks/sec over time)",
        hover_data=["elapsed_sec", "ticks", "commit"],
    )

    # === baseline lines ===
    for symbol, y_value in BASELINES.items():
        fig.add_hline(
            y=y_value,
            line_dash="dot",
            line_color="red",
            annotation_text=f"{symbol} baseline {y_value} ticks/sec",
            annotation_position="top right",
        )

    # === layout ===
    fig.update_layout(
        template="plotly_white",
        title_font=dict(size=20),
        xaxis_title="Timestamp (UTC)",
        yaxis_title="Ticks per second",
        legend_title="Symbol",
        hovermode="x unified",
        margin=dict(l=60, r=60, t=80, b=50),
    )

    # === save interactive HTML ===
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    fig.write_html(OUTPUT_HTML)
    print(f"✅ บันทึกไฟล์ interactive HTML → {OUTPUT_HTML}")

    # === save static PNG (Plotly ≥6.3, Kaleido + Chrome) ===
    try:
        import kaleido  # ensure kaleido backend loaded

        # ✅ set new default export configuration (no warnings)
        pio.defaults.default_format = "png"
        pio.defaults.default_scale = 2
        pio.defaults.default_width = 1200
        pio.defaults.default_height = 600
        pio.renderers.default = "kaleido"

        # ✅ check Chrome availability (Plotly ≥6)
        try:
            pio.kaleido.scope.chromium_path
        except Exception:
            print(
                "⚠️  ยังไม่พบ Chrome ในระบบ Kaleido\n"
                "👉 ติดตั้งด้วยคำสั่ง:  plotly_get_chrome\n"
                "   หรือ ติดตั้ง Google Chrome แล้วรันใหม่"
            )

        fig.write_image(OUTPUT_PNG, engine="kaleido")
        print(f"🖼️  บันทึกภาพ static PNG → {OUTPUT_PNG}")

    except Exception as e:
        print(f"⚠️  Export PNG ล้มเหลว: {e}")


# ------------------------------------------------------
def main():
    try:
        df = load_benchmark_data(RESULT_CSV)
        print(f"📚 โหลด benchmark สำเร็จ ({len(df)} records)")
        print(df.tail(5))
        plot_trend(df)
        print("🎯 เสร็จสิ้น — เปิดไฟล์ benchmark_trend.html เพื่อดูกราฟ")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")


# ------------------------------------------------------
if __name__ == "__main__":
    main()
