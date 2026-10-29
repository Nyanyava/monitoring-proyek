"""
Aplikasi Monitoring Keterlambatan Proyek (Streamlit)

Menu:
  1. Dashboard Utama   -> Early Warning System (3 data input, status Safe/Warning/Critical)
  2. Detail Kurva S    -> Progress Tracker per item pekerjaan + Kurva S
  3. Export Laporan    -> Download PDF atau Excel

Jalankan lokal:  streamlit run app.py
"""
import io
from datetime import date, datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

st.set_page_config(page_title="Monitoring Proyek", page_icon="🏗️", layout="wide")

# ----------------------------------------------------------------------------
# KONSTANTA
# ----------------------------------------------------------------------------
COL_NAMA = "Item Pekerjaan"
COL_BOBOT = "Bobot (%)"
COL_MULAI = "Mulai (hari ke)"
COL_DURASI = "Durasi (hari)"
COL_REAL = "Realisasi (%)"
COL_HARI = "Hari ke"
COL_RKUM = "Realisasi kumulatif (%)"

STATUS_STYLE = {
    "Safe": {"color": "#2e7d32", "rgb": (46, 125, 50), "icon": "🟢", "teks": "SAFE - Proyek sesuai jadwal"},
    "Warning": {"color": "#f9a825", "rgb": (230, 150, 0), "icon": "🟡", "teks": "WARNING - Mulai tertinggal dari rencana"},
    "Critical Delay": {"color": "#c62828", "rgb": (198, 40, 40), "icon": "🔴", "teks": "CRITICAL DELAY - Terlambat serius"},
}
ITEM_ICON = {"On track": "🟢", "Waspada": "🟡", "Terlambat": "🔴"}

DEFAULT_ITEMS = pd.DataFrame(
    {
        COL_NAMA: ["Persiapan", "Galian & Pondasi", "Struktur Beton", "Dinding & Atap", "MEP", "Finishing"],
        COL_BOBOT: [5.0, 15.0, 30.0, 20.0, 10.0, 20.0],
        COL_MULAI: [1, 8, 30, 60, 70, 90],
        COL_DURASI: [7, 22, 40, 35, 30, 30],
        COL_REAL: [100.0, 100.0, 60.0, 10.0, 0.0, 0.0],
    }
)
DEFAULT_RIWAYAT = pd.DataFrame(
    {COL_HARI: [0, 15, 30, 45], COL_RKUM: [0.0, 6.0, 14.0, 22.0]}
)


# ----------------------------------------------------------------------------
# STATE
# ----------------------------------------------------------------------------
def init_state():
    ss = st.session_state
    ss.setdefault("nama_proyek", "Proyek Contoh")
    ss.setdefault("tgl_mulai", date.today() - timedelta(days=45))
    ss.setdefault("tgl_acuan", date.today())
    ss.setdefault("durasi_total", 120)
    ss.setdefault("toleransi_warning", 2.0)
    ss.setdefault("batas_critical", 10.0)
    ss.setdefault("mode_data", "Manual (3 input)")
    ss.setdefault("m_target", 40.0)
    ss.setdefault("m_real", 32.0)
    ss.setdefault("m_sisa", 75)
    ss.setdefault("data_pekerjaan", DEFAULT_ITEMS.copy())
    ss.setdefault("riwayat", DEFAULT_RIWAYAT.copy())


# ----------------------------------------------------------------------------
# PERHITUNGAN
# ----------------------------------------------------------------------------
def clean_items(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[COL_NAMA] = df[COL_NAMA].fillna("").astype(str)
    for c in [COL_BOBOT, COL_MULAI, COL_DURASI, COL_REAL]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    df = df[(df[COL_NAMA].str.strip() != "") | (df[COL_BOBOT] > 0)]
    return df.reset_index(drop=True)


def clean_riwayat(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[COL_HARI] = pd.to_numeric(df[COL_HARI], errors="coerce")
    df[COL_RKUM] = pd.to_numeric(df[COL_RKUM], errors="coerce")
    return df.dropna().sort_values(COL_HARI).reset_index(drop=True)


def planned_curve(items: pd.DataFrame, total_days: int):
    """Kurva S rencana kumulatif (%) per hari, asumsi progres tiap item linear."""
    days = np.arange(0, total_days + 1)
    curve = np.zeros(len(days), dtype=float)
    for _, r in items.iterrows():
        mulai, durasi, bobot = float(r[COL_MULAI]), max(float(r[COL_DURASI]), 1.0), float(r[COL_BOBOT])
        curve += np.clip((days - (mulai - 1)) / durasi, 0, 1) * bobot
    total_bobot = items[COL_BOBOT].sum()
    if total_bobot > 0:
        curve = curve / total_bobot * 100
    return days, curve


def actual_total(items: pd.DataFrame) -> float:
    total_bobot = items[COL_BOBOT].sum()
    if total_bobot <= 0:
        return 0.0
    return float((items[COL_BOBOT] * items[COL_REAL] / 100).sum() / total_bobot * 100)


def hari_acuan() -> int:
    ss = st.session_state
    return int(np.clip((ss.tgl_acuan - ss.tgl_mulai).days, 0, int(ss.durasi_total)))


def hitung_status(target, real, sisa, toleransi, batas_critical):
    deviasi = real - target
    if real >= 100:
        status = "Safe"
    elif sisa <= 0:
        status = "Critical Delay"
    elif deviasi >= -toleransi:
        status = "Safe"
    elif deviasi >= -batas_critical:
        status = "Warning"
    else:
        status = "Critical Delay"
    laju = (100 - real) / sisa if sisa > 0 else None
    return deviasi, status, laju


def get_metrics() -> dict:
    ss = st.session_state
    total = int(ss.durasi_total)
    items = clean_items(ss["data_pekerjaan"])
    days, plan = planned_curve(items, total)

    if ss.mode_data.startswith("Otomatis"):
        elapsed = hari_acuan()
        target = float(np.interp(elapsed, days, plan))
        real = actual_total(items)
        sisa = total - elapsed
    else:
        target, real, sisa = float(ss.m_target), float(ss.m_real), int(ss.m_sisa)
        elapsed = max(total - sisa, 0)

    deviasi, status, laju = hitung_status(target, real, sisa, ss.toleransi_warning, ss.batas_critical)
    laju_rata = real / elapsed if elapsed > 0 else None
    return {
        "nama": ss.nama_proyek,
        "target": target,
        "real": real,
        "sisa": sisa,
        "elapsed": elapsed,
        "total": total,
        "deviasi": deviasi,
        "status": status,
        "laju": laju,
        "laju_rata": laju_rata,
        "days": days,
        "plan": plan,
        "items": items,
        "riwayat": clean_riwayat(ss.riwayat),
        "mode": ss.mode_data,
    }


def rekomendasi(m: dict) -> str:
    if m["real"] >= 100:
        return "Pekerjaan sudah selesai 100%."
    if m["sisa"] <= 0:
        return "Waktu kontrak sudah habis tetapi pekerjaan belum selesai. Segera ajukan addendum / percepatan dan evaluasi sumber daya."
    teks = f"Agar selesai tepat waktu, progres minimal yang harus dikejar adalah {m['laju']:.2f}% per hari."
    if m["laju_rata"]:
        rasio = m["laju"] / m["laju_rata"]
        if rasio > 1.05:
            teks += f" Itu sekitar {rasio:.1f}x lebih cepat dari laju rata-rata sejauh ini ({m['laju_rata']:.2f}%/hari)."
        else:
            teks += f" Laju rata-rata sejauh ini ({m['laju_rata']:.2f}%/hari) sudah cukup untuk mengejarnya."
    if m["status"] == "Warning":
        teks += " Disarankan menambah tenaga kerja/alat atau lembur pada pekerjaan kritis."
    elif m["status"] == "Critical Delay":
        teks += " Perlu tindakan percepatan segera (tambah sumber daya, shift kerja, re-sequencing) dan lapor ke manajemen."
    return teks


def tabel_per_item(items: pd.DataFrame, hari: int) -> pd.DataFrame:
    rows = []
    for _, r in items.iterrows():
        mulai, durasi = float(r[COL_MULAI]), max(float(r[COL_DURASI]), 1.0)
        rencana = float(np.clip((hari - (mulai - 1)) / durasi, 0, 1)) * 100
        real = float(r[COL_REAL])
        dev = real - rencana
        status = "On track" if dev >= -5 else ("Waspada" if dev >= -15 else "Terlambat")
        rows.append(
            {
                COL_NAMA: r[COL_NAMA],
                COL_BOBOT: float(r[COL_BOBOT]),
                "Rencana saat ini (%)": round(rencana, 1),
                COL_REAL: round(real, 1),
                "Deviasi (poin)": round(dev, 1),
                "Status": status,
            }
        )
    return pd.DataFrame(rows)


def kurva_s_df(m: dict) -> pd.DataFrame:
    df = pd.DataFrame({"Hari": m["days"], "Rencana (%)": np.round(m["plan"], 2)})
    r = m["riwayat"]
    if len(r) >= 2:
        aktual = np.interp(m["days"], r[COL_HARI], r[COL_RKUM])
        aktual = np.where(m["days"] <= r[COL_HARI].max(), aktual, np.nan)
        df["Realisasi (%)"] = np.round(aktual, 2)
    else:
        df["Realisasi (%)"] = np.nan
    return df


# ----------------------------------------------------------------------------
# EXPORT
# ----------------------------------------------------------------------------
def safe(text) -> str:
    """fpdf core font hanya mendukung latin-1."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def build_excel(m: dict) -> bytes:
    out = io.BytesIO()
    hari = hari_acuan() if m["mode"].startswith("Otomatis") else m["elapsed"]
    detail = tabel_per_item(m["items"], hari)
    kurva = kurva_s_df(m)

    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        wb = w.book
        judul = wb.add_format({"bold": True, "font_size": 14})
        head = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        status_fmt = wb.add_format(
            {"bold": True, "font_color": "white", "bg_color": STATUS_STYLE[m["status"]]["color"], "align": "center"}
        )

        # Sheet 1: Ringkasan
        ringkasan = pd.DataFrame(
            {
                "Parameter": [
                    "Nama proyek",
                    "Tanggal laporan",
                    "Target progres (%)",
                    "Realisasi progres (%)",
                    "Deviasi (poin %)",
                    "Sisa waktu (hari)",
                    "Laju minimal yang harus dikejar (%/hari)",
                    "Laju rata-rata sejauh ini (%/hari)",
                    "Status",
                    "Rekomendasi",
                ],
                "Nilai": [
                    m["nama"],
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                    round(m["target"], 2),
                    round(m["real"], 2),
                    round(m["deviasi"], 2),
                    m["sisa"],
                    round(m["laju"], 3) if m["laju"] is not None else "-",
                    round(m["laju_rata"], 3) if m["laju_rata"] is not None else "-",
                    m["status"],
                    rekomendasi(m),
                ],
            }
        )
        ringkasan.to_excel(w, sheet_name="Ringkasan", index=False, startrow=2)
        ws = w.sheets["Ringkasan"]
        ws.write(0, 0, "Laporan Analisis Risiko Keterlambatan Proyek", judul)
        ws.set_column(0, 0, 42)
        ws.set_column(1, 1, 90)
        ws.write(2, 0, "Parameter", head)
        ws.write(2, 1, "Nilai", head)
        ws.write(11, 1, m["status"], status_fmt)  # baris "Status"

        # Sheet 2: Detail pekerjaan
        detail.to_excel(w, sheet_name="Detail Pekerjaan", index=False)
        w.sheets["Detail Pekerjaan"].set_column(0, 0, 30)
        w.sheets["Detail Pekerjaan"].set_column(1, 5, 20)

        # Sheet 3: Kurva S + grafik
        kurva.to_excel(w, sheet_name="Kurva S", index=False)
        n = len(kurva)
        chart = wb.add_chart({"type": "line"})
        chart.add_series(
            {"name": "Rencana", "categories": ["Kurva S", 1, 0, n, 0], "values": ["Kurva S", 1, 1, n, 1]}
        )
        chart.add_series(
            {"name": "Realisasi", "categories": ["Kurva S", 1, 0, n, 0], "values": ["Kurva S", 1, 2, n, 2]}
        )
        chart.set_title({"name": "Kurva S"})
        chart.set_x_axis({"name": "Hari ke"})
        chart.set_y_axis({"name": "Progres kumulatif (%)", "min": 0, "max": 100})
        chart.set_size({"width": 760, "height": 380})
        w.sheets["Kurva S"].insert_chart("E2", chart)

    return out.getvalue()


def build_pdf(m: dict) -> bytes:
    hari = hari_acuan() if m["mode"].startswith("Otomatis") else m["elapsed"]
    detail = tabel_per_item(m["items"], hari)

    # grafik kurva S
    fig, ax = plt.subplots(figsize=(7.5, 3.3))
    ax.plot(m["days"], m["plan"], color="#1565c0", label="Rencana", linewidth=2)
    r = m["riwayat"]
    if len(r) > 0:
        ax.plot(r[COL_HARI], r[COL_RKUM], color="#e65100", marker="o", label="Realisasi", linewidth=2)
    ax.axvline(m["elapsed"], color="gray", linestyle="--", linewidth=1)
    ax.scatter([m["elapsed"]], [m["real"]], color="black", zorder=5, label="Posisi saat ini")
    ax.set_xlabel("Hari ke")
    ax.set_ylabel("Progres kumulatif (%)")
    ax.set_ylim(0, 100)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Laporan Analisis Risiko Keterlambatan Proyek", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, safe(f"Proyek: {m['nama']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Tanggal laporan: {datetime.now().strftime('%d-%m-%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # banner status
    pdf.set_fill_color(*STATUS_STYLE[m["status"]]["rgb"])
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, safe(STATUS_STYLE[m["status"]]["teks"]), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    # ringkasan angka
    pdf.set_font("Helvetica", "", 11)
    baris = [
        ("Target progres", f"{m['target']:.1f} %"),
        ("Realisasi progres", f"{m['real']:.1f} %"),
        ("Deviasi", f"{m['deviasi']:+.1f} poin"),
        ("Sisa waktu", f"{m['sisa']} hari"),
        ("Laju minimal yang harus dikejar", f"{m['laju']:.2f} %/hari" if m["laju"] is not None else "-"),
        ("Laju rata-rata sejauh ini", f"{m['laju_rata']:.2f} %/hari" if m["laju_rata"] is not None else "-"),
    ]
    for k, v in baris:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(80, 7, k, border=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(60, 7, v, border=1, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Rekomendasi", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, safe(rekomendasi(m)), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.image(buf, w=180)
    pdf.ln(2)

    # tabel detail
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Detail Progres per Item Pekerjaan", new_x="LMARGIN", new_y="NEXT")
    lebar = [60, 22, 32, 28, 26, 22]
    judul_kol = ["Item", "Bobot %", "Rencana %", "Real. %", "Dev.", "Status"]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(217, 225, 242)
    for w_, t in zip(lebar, judul_kol):
        pdf.cell(w_, 7, t, border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for _, r_ in detail.iterrows():
        vals = [
            safe(r_[COL_NAMA])[:32],
            f"{r_[COL_BOBOT]:.1f}",
            f"{r_['Rencana saat ini (%)']:.1f}",
            f"{r_[COL_REAL]:.1f}",
            f"{r_['Deviasi (poin)']:+.1f}",
            r_["Status"],
        ]
        for w_, t in zip(lebar, vals):
            pdf.cell(w_, 6, t, border=1)
        pdf.ln()

    return bytes(pdf.output())


# ----------------------------------------------------------------------------
# HALAMAN
# ----------------------------------------------------------------------------
def sidebar() -> str:
    with st.sidebar:
        st.title("🏗️ Monitoring Proyek")
        halaman = st.radio("Menu", ["Dashboard Utama", "Detail Kurva S", "Export Laporan"])
        st.divider()
        with st.expander("⚙️ Pengaturan Proyek", expanded=False):
            st.text_input("Nama proyek", key="nama_proyek")
            st.date_input("Tanggal mulai proyek", key="tgl_mulai")
            st.number_input("Durasi kontrak (hari)", min_value=1, step=1, key="durasi_total")
            st.date_input("Tanggal acuan (hari ini)", key="tgl_acuan")
            st.number_input(
                "Toleransi Safe (poin %)", min_value=0.0, step=0.5, key="toleransi_warning",
                help="Deviasi sampai -X poin masih dianggap Safe.",
            )
            st.number_input(
                "Batas Critical (poin %)", min_value=0.0, step=0.5, key="batas_critical",
                help="Deviasi lebih buruk dari -X poin dianggap Critical Delay.",
            )
            st.radio(
                "Sumber data dashboard",
                ["Manual (3 input)", "Otomatis dari Detail Kurva S"],
                key="mode_data",
            )
        st.caption("Data tersimpan per sesi browser. Gunakan menu Export untuk menyimpan laporan.")
    return halaman


def page_dashboard():
    ss = st.session_state
    st.title(f"📊 Dashboard Utama - {ss.nama_proyek}")
    st.caption("Early Warning System keterlambatan proyek")

    if ss.mode_data.startswith("Manual"):
        c1, c2, c3 = st.columns(3)
        ss["m_target"] = c1.number_input("Target progres saat ini (%)", 0.0, 100.0, float(ss.m_target), step=0.5)
        ss["m_real"] = c2.number_input("Realisasi progres saat ini (%)", 0.0, 100.0, float(ss.m_real), step=0.5)
        ss["m_sisa"] = c3.number_input("Sisa waktu proyek (hari)", 0, 5000, int(ss.m_sisa), step=1)
    else:
        st.info(
            "Mode otomatis: target dihitung dari Kurva S rencana dan realisasi dari input per item "
            "di menu **Detail Kurva S**, pada tanggal acuan di Pengaturan Proyek."
        )

    m = get_metrics()
    gaya = STATUS_STYLE[m["status"]]

    st.markdown(
        f"""<div style="background:{gaya['color']};padding:18px;border-radius:12px;
        text-align:center;color:white;font-size:26px;font-weight:700;margin:10px 0 18px 0;">
        {gaya['icon']} {gaya['teks']}</div>""",
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Target", f"{m['target']:.1f}%")
    k2.metric("Realisasi", f"{m['real']:.1f}%", delta=f"{m['deviasi']:+.1f} poin")
    k3.metric("Sisa waktu", f"{m['sisa']} hari")
    k4.metric("Laju minimal", f"{m['laju']:.2f} %/hari" if m["laju"] is not None else "-")
    k5.metric("Laju rata-rata", f"{m['laju_rata']:.2f} %/hari" if m["laju_rata"] is not None else "-")

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=m["real"],
            number={"suffix": "%"},
            title={"text": "Realisasi vs Target (garis hitam = target)"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": gaya["color"]},
                "threshold": {"line": {"color": "black", "width": 4}, "value": m["target"]},
            },
        )
    )
    fig.update_layout(height=300, margin=dict(t=60, b=10, l=30, r=30))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Rekomendasi")
    st.write(rekomendasi(m))
    st.caption("Lihat grafik Kurva S dan progres per item di menu **Detail Kurva S**. Unduh laporan di menu **Export Laporan**.")


def page_kurva_s():
    ss = st.session_state
    st.title("📈 Detail Kurva S per Item Pekerjaan")

    st.subheader("1. Item pekerjaan (rencana & realisasi)")
    st.caption("Bobot total idealnya 100%. Klik baris terakhir untuk menambah item, pilih baris lalu Delete untuk menghapus.")
    edited = st.data_editor(
        ss["data_pekerjaan"],
        num_rows="dynamic",
        width="stretch",
        column_config={
            COL_NAMA: st.column_config.TextColumn(COL_NAMA),
            COL_BOBOT: st.column_config.NumberColumn(COL_BOBOT, min_value=0.0, max_value=100.0, step=0.5),
            COL_MULAI: st.column_config.NumberColumn(COL_MULAI, min_value=1, step=1),
            COL_DURASI: st.column_config.NumberColumn(COL_DURASI, min_value=1, step=1),
            COL_REAL: st.column_config.NumberColumn(COL_REAL, min_value=0.0, max_value=100.0, step=1.0),
        },
        key="editor_items",
    )
    ss["data_pekerjaan"] = edited
    items = clean_items(edited)

    total_bobot = items[COL_BOBOT].sum()
    if abs(total_bobot - 100) > 0.01:
        st.warning(f"Total bobot saat ini {total_bobot:.1f}%. Perhitungan dinormalisasi ke 100%.")

    st.subheader("2. Riwayat realisasi kumulatif (opsional, untuk garis aktual)")
    ss.riwayat = st.data_editor(
        ss.riwayat,
        num_rows="dynamic",
        width="stretch",
        column_config={
            COL_HARI: st.column_config.NumberColumn(COL_HARI, min_value=0, step=1),
            COL_RKUM: st.column_config.NumberColumn(COL_RKUM, min_value=0.0, max_value=100.0, step=0.5),
        },
        key="editor_riwayat",
    )

    total = int(ss.durasi_total)
    days, plan = planned_curve(items, total)
    hari = hari_acuan()
    target = float(np.interp(hari, days, plan))
    real = actual_total(items)
    riwayat = clean_riwayat(ss.riwayat)

    st.subheader("3. Kurva S")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=plan, name="Rencana", line=dict(color="#1565c0", width=3)))
    if len(riwayat) > 0:
        fig.add_trace(
            go.Scatter(
                x=riwayat[COL_HARI], y=riwayat[COL_RKUM], name="Realisasi (riwayat)",
                mode="lines+markers", line=dict(color="#e65100", width=3),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[hari], y=[real], name="Realisasi saat ini (dari item)", mode="markers",
            marker=dict(size=14, color="black", symbol="star"),
        )
    )
    fig.add_vline(x=hari, line_dash="dash", line_color="gray", annotation_text="Hari acuan")
    fig.update_layout(
        xaxis_title="Hari ke", yaxis_title="Progres kumulatif (%)", yaxis_range=[0, 100],
        height=450, legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, width="stretch")

    c1, c2, c3 = st.columns(3)
    c1.metric("Hari acuan", f"ke-{hari} dari {total}")
    c2.metric("Target (rencana)", f"{target:.1f}%")
    c3.metric("Realisasi (dari item)", f"{real:.1f}%", delta=f"{real - target:+.1f} poin")

    st.subheader("4. Status per item pekerjaan")
    detail = tabel_per_item(items, hari)
    tampil = detail.copy()
    tampil["Status"] = tampil["Status"].map(lambda s: f"{ITEM_ICON[s]} {s}")
    st.dataframe(tampil, width="stretch", hide_index=True)

    bar = go.Figure()
    bar.add_bar(x=detail[COL_NAMA], y=detail["Rencana saat ini (%)"], name="Rencana", marker_color="#1565c0")
    bar.add_bar(x=detail[COL_NAMA], y=detail[COL_REAL], name="Realisasi", marker_color="#e65100")
    bar.update_layout(barmode="group", yaxis_title="Progres item (%)", yaxis_range=[0, 100], height=380)
    st.plotly_chart(bar, width="stretch")


def page_export():
    st.title("📄 Export Laporan")
    m = get_metrics()
    gaya = STATUS_STYLE[m["status"]]
    st.markdown(f"**Status saat ini:** {gaya['icon']} {gaya['teks']}")
    st.write(
        f"Target **{m['target']:.1f}%**, realisasi **{m['real']:.1f}%**, "
        f"sisa waktu **{m['sisa']} hari**."
    )
    st.write(rekomendasi(m))
    st.divider()

    nama_file = "".join(ch if ch.isalnum() else "_" for ch in m["nama"]) or "proyek"
    tgl = datetime.now().strftime("%Y%m%d")
    c1, c2 = st.columns(2)
    try:
        c1.download_button(
            "⬇️ Download PDF", data=build_pdf(m), file_name=f"laporan_{nama_file}_{tgl}.pdf",
            mime="application/pdf", width="stretch",
        )
    except Exception as e:
        c1.error(f"Gagal membuat PDF: {e}")
    try:
        c2.download_button(
            "⬇️ Download Excel", data=build_excel(m), file_name=f"laporan_{nama_file}_{tgl}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch",
        )
    except Exception as e:
        c2.error(f"Gagal membuat Excel: {e}")


def main():
    init_state()
    halaman = sidebar()
    if halaman == "Dashboard Utama":
        page_dashboard()
    elif halaman == "Detail Kurva S":
        page_kurva_s()
    else:
        page_export()


main()
