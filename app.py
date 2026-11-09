"""
Aplikasi Monitoring & Early Warning Keterlambatan Proyek (Streamlit) - Versi 2

Semua data awal dikosongkan. Isi sendiri melalui:
  - Sidebar > Pengaturan Proyek
  - Dashboard Utama (3 input) atau Detail Kurva S (tabel item)

Menu:
  1. Dashboard Utama   -> Early Warning (target, realisasi, sisa waktu)
  2. Detail Kurva S    -> Progress tracker per item + Kurva S
  3. Export Laporan    -> Download PDF atau Excel

Jalankan lokal:  python -m streamlit run app.py
"""
import io
from datetime import date, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from fpdf import FPDF

st.set_page_config(page_title="Monitoring Proyek", page_icon="🏗️", layout="wide")
S = st.session_state

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

MODE_MANUAL = "Manual (3 input)"
MODE_AUTO = "Otomatis dari Detail Kurva S"

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
         "September", "Oktober", "November", "Desember"]

INK = "#0F2A43"
BLUEPRINT = "#1D4E89"
ACTUAL = "#D9480F"

STATUS_STYLE = {
    "Safe": {"color": "#15803D", "rgb": (21, 128, 61), "icon": "🟢",
             "judul": "Safe", "teks": "SAFE - Proyek sesuai jadwal",
             "sub": "Progres berada dalam batas toleransi terhadap rencana."},
    "Warning": {"color": "#D97706", "rgb": (217, 119, 6), "icon": "🟡",
                "judul": "Warning", "teks": "WARNING - Mulai tertinggal dari rencana",
                "sub": "Deviasi mulai melebar. Perlu percepatan ringan."},
    "Critical Delay": {"color": "#B91C1C", "rgb": (185, 28, 28), "icon": "🔴",
                       "judul": "Critical Delay", "teks": "CRITICAL DELAY - Terlambat serius",
                       "sub": "Perlu tindakan percepatan segera dan laporan ke manajemen."},
}
ITEM_ICON = {"On track": "🟢", "Waspada": "🟡", "Terlambat": "🔴"}

NAV = {"dashboard": "📊  Dashboard Utama", "kurva": "📈  Detail Kurva S", "export": "📄  Export Laporan"}

# ----------------------------------------------------------------------------
# TAMPILAN (CSS)
# ----------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Manrope', 'Segoe UI', sans-serif; }
.stApp { background: #F3F6F9; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 1.6rem; max-width: 1240px; }
[data-testid="stSidebar"] { background: #E8EEF4; border-right: 1px solid #D5DEE8; }

.brand { background:#0F2A43; color:#fff; border-radius:12px; padding:14px 16px; margin-bottom:14px;
  border-bottom:4px solid #F5B700; }
.brand .b1 { font-family:'Space Grotesk',sans-serif; font-size:19px; font-weight:700; letter-spacing:.2px; }
.brand .b2 { font-size:12.5px; opacity:.8; margin-top:2px; }

.hero { background-color:#0F2A43;
  background-image: linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px);
  background-size: 26px 26px; border-radius:14px; padding:26px 30px; color:#fff;
  border-bottom:5px solid #F5B700; margin-bottom:18px; }
.hero .t { font-family:'Space Grotesk',sans-serif; font-size:32px; font-weight:700; line-height:1.15; color:#fff; }
.hero .s { font-size:15px; opacity:.85; margin-top:6px; color:#fff; }
.chip { display:inline-block; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25);
  border-radius:999px; padding:4px 13px; font-size:12.5px; font-weight:600; margin:12px 8px 0 0; color:#fff; }

.banner { border-radius:14px; padding:22px 26px; color:#fff; margin:4px 0 16px; display:flex; align-items:center; gap:20px;
  background-image: repeating-linear-gradient(135deg, rgba(255,255,255,.07) 0 14px, transparent 14px 28px); }
.banner .big { font-size:46px; line-height:1; }
.banner .t { font-family:'Space Grotesk',sans-serif; font-size:30px; font-weight:700; line-height:1.1; color:#fff; }
.banner .s { font-size:14.5px; opacity:.95; margin-top:5px; color:#fff; }

.strip { display:grid; grid-template-columns:repeat(auto-fit,minmax(175px,1fr)); gap:1px; background:#D5DEE8;
  border:1px solid #D5DEE8; border-radius:14px; overflow:hidden; margin-bottom:16px; }
.cell { background:#fff; padding:16px 18px; }
.cell .l { font-size:13px; font-weight:600; color:#5B6B7D; }
.cell .v { font-family:'Space Grotesk',sans-serif; font-size:30px; font-weight:700; color:#0F2A43; line-height:1.2; margin-top:2px; }
.cell .u { font-size:14px; font-weight:600; color:#5B6B7D; margin-left:3px; }
.cell .d { font-size:12.5px; color:#5B6B7D; margin-top:2px; }

.card { background:#fff; border:1px solid #D5DEE8; border-radius:14px; padding:18px 20px; color:#0F2A43; margin-bottom:14px; }
.card .h { font-size:16px; font-weight:700; margin-bottom:6px; color:#0F2A43; }
.card p { color:#334155; margin:4px 0; line-height:1.6; }
.bar-row { display:flex; align-items:center; gap:12px; margin:12px 0; font-size:14px; color:#0F2A43; }
.bar-row .n { width:78px; color:#5B6B7D; font-weight:600; }
.bar-row .v { width:58px; text-align:right; font-weight:700; font-family:'Space Grotesk',sans-serif; }
.track { flex:1; background:#E3E9F0; border-radius:999px; height:14px; overflow:hidden; }
.fill { height:100%; border-radius:999px; }

.empty { background:#fff; border:2px dashed #B6C4D4; border-radius:14px; padding:34px 30px; text-align:center; color:#0F2A43; }
.empty .e1 { font-size:42px; }
.empty .e2 { font-family:'Space Grotesk',sans-serif; font-size:22px; font-weight:700; margin-top:6px; }
.empty .e3 { color:#475569; margin-top:6px; line-height:1.6; }

.sec { font-family:'Space Grotesk',sans-serif; font-size:19px; font-weight:700; color:#0F2A43; margin:6px 0 8px; }

.stDownloadButton button { border-radius:12px; font-weight:700; padding:.75rem 1rem; border:none;
  background:#1D4E89; color:#fff; }
.stDownloadButton button:hover { background:#0F2A43; color:#fff; }
.stDownloadButton button p { color:#fff; }
</style>
"""


def tgl_id(d) -> str:
    return f"{d.day} {BULAN[d.month - 1]} {d.year}"


def fmt(v, nd=1, suffix=""):
    return "-" if v is None else f"{v:.{nd}f}{suffix}".replace(".", ",")


# ----------------------------------------------------------------------------
# STATE (semua kosong)
# ----------------------------------------------------------------------------
def blank_items(n=6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_NAMA: pd.Series([None] * n, dtype="object"),
            COL_BOBOT: [np.nan] * n,
            COL_MULAI: [np.nan] * n,
            COL_DURASI: [np.nan] * n,
            COL_REAL: [np.nan] * n,
        }
    )


def blank_riwayat(n=5) -> pd.DataFrame:
    return pd.DataFrame({COL_HARI: [np.nan] * n, COL_RKUM: [np.nan] * n})


def init_state():
    defaults = {
        "nama_proyek": "",
        "tgl_mulai": date.today(),
        "tgl_acuan": date.today(),
        "durasi_total": None,
        "toleransi_warning": 2.0,
        "batas_critical": 10.0,
        "mode_data": MODE_MANUAL,
        "m_target": None,
        "m_real": None,
        "m_sisa": None,
        "data_pekerjaan": blank_items(),
        "riwayat": blank_riwayat(),
    }
    for k, v in defaults.items():
        if k not in S:
            S[k] = v


def reset_all():
    for k in list(S.keys()):
        del S[k]


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
    total = int(S["durasi_total"] or 0)
    return int(np.clip((S["tgl_acuan"] - S["tgl_mulai"]).days, 0, total))


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
    total = int(S["durasi_total"] or 0)
    items = clean_items(S["data_pekerjaan"])
    bobot_sum = float(items[COL_BOBOT].sum()) if len(items) else 0.0
    has_curve = total > 0 and bobot_sum > 0
    if has_curve:
        days, plan = planned_curve(items, total)
    else:
        days, plan = np.array([0]), np.array([0.0])

    auto = S["mode_data"] == MODE_AUTO
    if auto:
        ready = has_curve
        elapsed = hari_acuan() if has_curve else None
        target = float(np.interp(elapsed, days, plan)) if has_curve else 0.0
        real = actual_total(items)
        sisa = total - (elapsed or 0)
    else:
        vals = [S["m_target"], S["m_real"], S["m_sisa"]]
        ready = all(v is not None for v in vals)
        if ready:
            target, real, sisa = float(S["m_target"]), float(S["m_real"]), int(S["m_sisa"])
            elapsed = total - sisa if (total > 0 and 0 <= sisa <= total) else None
        else:
            target, real, sisa, elapsed = 0.0, 0.0, 0, None

    if ready:
        deviasi, status, laju = hitung_status(target, real, sisa, S["toleransi_warning"], S["batas_critical"])
    else:
        deviasi, status, laju = 0.0, None, None
    laju_rata = real / elapsed if (ready and elapsed) else None

    return {
        "ready": ready, "auto": auto, "has_curve": has_curve,
        "nama": S["nama_proyek"].strip() or "Proyek Tanpa Nama",
        "target": target, "real": real, "sisa": sisa, "elapsed": elapsed, "total": total,
        "deviasi": deviasi, "status": status, "laju": laju, "laju_rata": laju_rata,
        "days": days, "plan": plan, "items": items,
        "riwayat": clean_riwayat(S["riwayat"]),
        "mode": S["mode_data"],
    }


def rekomendasi(m: dict) -> str:
    if m["real"] >= 100:
        return "Pekerjaan sudah selesai 100%."
    if m["sisa"] <= 0:
        return ("Waktu kontrak sudah habis tetapi pekerjaan belum selesai. Segera ajukan addendum "
                "atau percepatan, dan evaluasi sumber daya.")
    teks = f"Agar selesai tepat waktu, progres minimal yang harus dikejar adalah {m['laju']:.2f}% per hari."
    if m["laju_rata"]:
        rasio = m["laju"] / m["laju_rata"]
        if rasio > 1.05:
            teks += (f" Itu sekitar {rasio:.1f}x lebih cepat dari laju rata-rata sejauh ini "
                     f"({m['laju_rata']:.2f}%/hari).")
        else:
            teks += f" Laju rata-rata sejauh ini ({m['laju_rata']:.2f}%/hari) sudah cukup untuk mengejarnya."
    if m["status"] == "Warning":
        teks += " Disarankan menambah tenaga kerja atau alat, atau lembur pada pekerjaan kritis."
    elif m["status"] == "Critical Delay":
        teks += (" Perlu tindakan percepatan segera (tambah sumber daya, shift kerja, urutan ulang pekerjaan) "
                 "dan laporkan ke manajemen.")
    return teks


def tabel_per_item(items: pd.DataFrame, hari) -> pd.DataFrame:
    cols = [COL_NAMA, COL_BOBOT, "Rencana saat ini (%)", COL_REAL, "Deviasi (poin)", "Status"]
    if hari is None or len(items) == 0:
        return pd.DataFrame(columns=cols)
    rows = []
    for _, r in items.iterrows():
        mulai, durasi = float(r[COL_MULAI]), max(float(r[COL_DURASI]), 1.0)
        rencana = float(np.clip((hari - (mulai - 1)) / durasi, 0, 1)) * 100
        real = float(r[COL_REAL])
        dev = real - rencana
        status = "On track" if dev >= -5 else ("Waspada" if dev >= -15 else "Terlambat")
        rows.append({
            COL_NAMA: r[COL_NAMA] or "(tanpa nama)", COL_BOBOT: float(r[COL_BOBOT]),
            "Rencana saat ini (%)": round(rencana, 1), COL_REAL: round(real, 1),
            "Deviasi (poin)": round(dev, 1), "Status": status,
        })
    return pd.DataFrame(rows, columns=cols)


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


def hari_untuk_detail(m: dict):
    return hari_acuan() if (m["auto"] and m["has_curve"]) else m["elapsed"]


# ----------------------------------------------------------------------------
# EXPORT
# ----------------------------------------------------------------------------
def safe(text) -> str:
    return str(text).encode("latin-1", "replace").decode("latin-1")


def build_excel(m: dict) -> bytes:
    out = io.BytesIO()
    detail = tabel_per_item(m["items"], hari_untuk_detail(m))
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        wb = w.book
        judul = wb.add_format({"bold": True, "font_size": 14})
        head = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        status_fmt = wb.add_format(
            {"bold": True, "font_color": "white", "bg_color": STATUS_STYLE[m["status"]]["color"], "align": "center"}
        )
        ringkasan = pd.DataFrame({
            "Parameter": ["Nama proyek", "Tanggal laporan", "Target progres (%)", "Realisasi progres (%)",
                          "Deviasi (poin %)", "Sisa waktu (hari)", "Laju minimal yang harus dikejar (%/hari)",
                          "Laju rata-rata sejauh ini (%/hari)", "Status", "Rekomendasi"],
            "Nilai": [m["nama"], datetime.now().strftime("%d-%m-%Y %H:%M"), round(m["target"], 2),
                      round(m["real"], 2), round(m["deviasi"], 2), m["sisa"],
                      round(m["laju"], 3) if m["laju"] is not None else "-",
                      round(m["laju_rata"], 3) if m["laju_rata"] is not None else "-",
                      m["status"], rekomendasi(m)],
        })
        ringkasan.to_excel(w, sheet_name="Ringkasan", index=False, startrow=2)
        ws = w.sheets["Ringkasan"]
        ws.write(0, 0, "Laporan Analisis Risiko Keterlambatan Proyek", judul)
        ws.set_column(0, 0, 42)
        ws.set_column(1, 1, 90)
        ws.write(2, 0, "Parameter", head)
        ws.write(2, 1, "Nilai", head)
        ws.write(11, 1, m["status"], status_fmt)

        if len(detail) > 0:
            detail.to_excel(w, sheet_name="Detail Pekerjaan", index=False)
            w.sheets["Detail Pekerjaan"].set_column(0, 0, 30)
            w.sheets["Detail Pekerjaan"].set_column(1, 5, 20)

        if m["has_curve"]:
            kurva = kurva_s_df(m)
            kurva.to_excel(w, sheet_name="Kurva S", index=False)
            n = len(kurva)
            chart = wb.add_chart({"type": "line"})
            chart.add_series({"name": "Rencana", "categories": ["Kurva S", 1, 0, n, 0], "values": ["Kurva S", 1, 1, n, 1]})
            chart.add_series({"name": "Realisasi", "categories": ["Kurva S", 1, 0, n, 0], "values": ["Kurva S", 1, 2, n, 2]})
            chart.set_title({"name": "Kurva S"})
            chart.set_x_axis({"name": "Hari ke"})
            chart.set_y_axis({"name": "Progres kumulatif (%)", "min": 0, "max": 100})
            chart.set_size({"width": 760, "height": 380})
            w.sheets["Kurva S"].insert_chart("E2", chart)
    return out.getvalue()


def build_pdf(m: dict) -> bytes:
    detail = tabel_per_item(m["items"], hari_untuk_detail(m))
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Laporan Analisis Risiko Keterlambatan Proyek", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, safe(f"Proyek: {m['nama']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Tanggal laporan: {datetime.now().strftime('%d-%m-%Y %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_fill_color(*STATUS_STYLE[m["status"]]["rgb"])
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 12, safe(STATUS_STYLE[m["status"]]["teks"]), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

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

    if m["has_curve"]:
        fig, ax = plt.subplots(figsize=(7.5, 3.3))
        ax.plot(m["days"], m["plan"], color=BLUEPRINT, label="Rencana", linewidth=2)
        r = m["riwayat"]
        if len(r) > 0:
            ax.plot(r[COL_HARI], r[COL_RKUM], color=ACTUAL, marker="o", label="Realisasi", linewidth=2)
        if m["elapsed"] is not None:
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
        pdf.image(buf, w=180)
        pdf.ln(2)

    if len(detail) > 0:
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
            vals = [safe(r_[COL_NAMA])[:32], f"{r_[COL_BOBOT]:.1f}", f"{r_['Rencana saat ini (%)']:.1f}",
                    f"{r_[COL_REAL]:.1f}", f"{r_['Deviasi (poin)']:+.1f}", r_["Status"]]
            for w_, t in zip(lebar, vals):
                pdf.cell(w_, 6, t, border=1)
            pdf.ln()
    return bytes(pdf.output())


# ----------------------------------------------------------------------------
# KOMPONEN TAMPILAN
# ----------------------------------------------------------------------------
def hero(judul: str, sub: str, chips=()):
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    st.markdown(f'<div class="hero"><div class="t">{judul}</div><div class="s">{sub}</div>{chip_html}</div>',
                unsafe_allow_html=True)


def strip(cells):
    html = ""
    for label, value, unit, desc in cells:
        u = f'<span class="u">{unit}</span>' if unit else ""
        html += f'<div class="cell"><div class="l">{label}</div><div class="v">{value}{u}</div><div class="d">{desc}</div></div>'
    st.markdown(f'<div class="strip">{html}</div>', unsafe_allow_html=True)


def empty_state(ikon, judul, teks):
    st.markdown(f'<div class="empty"><div class="e1">{ikon}</div><div class="e2">{judul}</div><div class="e3">{teks}</div></div>',
                unsafe_allow_html=True)


def style_fig(fig, height=420):
    fig.update_layout(
        template="plotly_white", height=height, margin=dict(t=50, b=40, l=50, r=20),
        font=dict(family="Manrope, Segoe UI, sans-serif", color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.22),
    )
    return fig


def gauge(m: dict):
    tol, crit = float(S["toleransi_warning"]), float(S["batas_critical"])
    lo_crit, lo_warn = max(m["target"] - crit, 0), max(m["target"] - tol, 0)
    steps = [{"range": [0, lo_crit], "color": "#FECACA"},
             {"range": [lo_crit, lo_warn], "color": "#FDE68A"},
             {"range": [lo_warn, 100], "color": "#BBF7D0"}]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=m["real"], number={"suffix": "%", "font": {"family": "Space Grotesk", "size": 44}},
        title={"text": "Realisasi dibanding zona target"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": STATUS_STYLE[m["status"]]["color"], "thickness": 0.28},
               "steps": steps, "threshold": {"line": {"color": INK, "width": 5}, "thickness": 0.85, "value": m["target"]}},
    ))
    style_fig(fig, 320)
    fig.update_layout(margin=dict(t=60, b=10, l=30, r=30))
    return fig


def bars_html(m: dict):
    color = STATUS_STYLE[m["status"]]["color"]
    t, r = min(max(m["target"], 0), 100), min(max(m["real"], 0), 100)
    return f"""<div class="card"><div class="h">Target dibanding realisasi</div>
      <div class="bar-row"><span class="n">Target</span><div class="track"><div class="fill" style="width:{t}%;background:{BLUEPRINT}"></div></div><span class="v">{m['target']:.1f}%</span></div>
      <div class="bar-row"><span class="n">Realisasi</span><div class="track"><div class="fill" style="width:{r}%;background:{color}"></div></div><span class="v">{m['real']:.1f}%</span></div></div>"""


# ----------------------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------------------
def sidebar() -> str:
    with st.sidebar:
        st.markdown('<div class="brand"><div class="b1">🏗️ Monitoring Proyek</div>'
                    '<div class="b2">Deteksi dini keterlambatan</div></div>', unsafe_allow_html=True)
        halaman = st.radio("Menu", list(NAV.keys()), format_func=lambda k: NAV[k], label_visibility="collapsed")
        st.divider()
        with st.expander("⚙️ Pengaturan proyek", expanded=True):
            st.text_input("Nama proyek", key="nama_proyek", placeholder="Contoh: Gedung Kantor 2 Lantai")
            st.date_input("Tanggal mulai proyek", key="tgl_mulai", format="DD/MM/YYYY")
            st.number_input("Durasi kontrak (hari)", min_value=1, step=1, value=None, key="durasi_total",
                            placeholder="Contoh: 120")
            st.date_input("Tanggal acuan (hari ini)", key="tgl_acuan", format="DD/MM/YYYY")
            st.number_input("Toleransi Safe (poin %)", min_value=0.0, step=0.5, key="toleransi_warning",
                            help="Deviasi sampai -X poin masih dianggap Safe.")
            st.number_input("Batas Critical (poin %)", min_value=0.0, step=0.5, key="batas_critical",
                            help="Deviasi lebih buruk dari -X poin dianggap Critical Delay.")
            st.radio("Sumber data dashboard", [MODE_MANUAL, MODE_AUTO], key="mode_data")
        st.button("🗑️ Kosongkan semua data", on_click=reset_all, width="stretch")
        st.caption("Data tersimpan per sesi browser. Gunakan menu Export untuk menyimpan laporan.")
    return halaman


# ----------------------------------------------------------------------------
# HALAMAN
# ----------------------------------------------------------------------------
def page_dashboard():
    nama = S["nama_proyek"].strip() or "Proyek Anda"
    chips = [f"📅 Mulai {tgl_id(S['tgl_mulai'])}", f"📍 Acuan {tgl_id(S['tgl_acuan'])}",
             "✍️ Mode manual" if S["mode_data"] == MODE_MANUAL else "⚙️ Mode otomatis"]
    if S["durasi_total"]:
        chips.insert(1, f"⏱️ Kontrak {int(S['durasi_total'])} hari")
    hero(nama, "Dashboard utama: status kesehatan proyek dalam sekali lihat", chips)

    if S["mode_data"] == MODE_MANUAL:
        with st.container(border=True):
            st.markdown('<div class="sec">Isi 3 data berikut</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            S["m_target"] = c1.number_input("🎯 Target progres saat ini (%)", min_value=0.0, max_value=100.0,
                                            value=S["m_target"], step=0.5, placeholder="Contoh: 32")
            S["m_real"] = c2.number_input("📈 Realisasi progres saat ini (%)", min_value=0.0, max_value=100.0,
                                          value=S["m_real"], step=0.5, placeholder="Contoh: 29")
            S["m_sisa"] = c3.number_input("⏳ Sisa waktu proyek (hari)", min_value=0, step=1,
                                          value=S["m_sisa"], placeholder="Contoh: 75")
    else:
        st.info("Mode otomatis: target dihitung dari Kurva S rencana, realisasi dari tabel item, dan sisa waktu "
                "dari durasi kontrak. Isi datanya di menu **Detail Kurva S** dan durasi di **Pengaturan proyek**.")

    m = get_metrics()
    if not m["ready"]:
        if m["auto"]:
            empty_state("🧱", "Data belum lengkap",
                        "Isi durasi kontrak di Pengaturan proyek, lalu isi tabel item pekerjaan (bobot, mulai, durasi) "
                        "di menu Detail Kurva S.")
        else:
            empty_state("📝", "Belum ada data",
                        "Isi target progres, realisasi progres, dan sisa waktu di atas. "
                        "Status proyek akan muncul di sini.")
        return

    gaya = STATUS_STYLE[m["status"]]
    st.markdown(
        f'<div class="banner" style="background-color:{gaya["color"]}"><div class="big">{gaya["icon"]}</div>'
        f'<div><div class="t">{gaya["judul"]}</div><div class="s">{gaya["sub"]}</div></div></div>',
        unsafe_allow_html=True,
    )

    strip([
        ("Target", fmt(m["target"]), "%", "Seharusnya sudah tercapai"),
        ("Realisasi", fmt(m["real"]), "%", f"Deviasi {m['deviasi']:+.1f} poin".replace(".", ",")),
        ("Sisa waktu", f"{m['sisa']}", "hari", "Hingga akhir kontrak"),
        ("Laju minimal", fmt(m["laju"], 2), "%/hari" if m["laju"] is not None else "", "Agar selesai tepat waktu"),
        ("Laju rata-rata", fmt(m["laju_rata"], 2), "%/hari" if m["laju_rata"] is not None else "", "Sejauh ini"),
    ])

    kiri, kanan = st.columns([1, 1])
    with kiri:
        st.plotly_chart(gauge(m), width="stretch")
        st.caption("Garis hitam = target. Zona hijau = Safe, kuning = Warning, merah = Critical Delay.")
    with kanan:
        st.markdown(bars_html(m), unsafe_allow_html=True)
        st.markdown(f'<div class="card"><div class="h">Rekomendasi</div><p>{rekomendasi(m)}</p></div>',
                    unsafe_allow_html=True)
    st.caption("Rincian per item ada di menu **Detail Kurva S**. Unduh laporan di menu **Export Laporan**.")


def page_kurva_s():
    hero("Detail Kurva S", "Progres per item pekerjaan, dari rencana sampai realisasi",
         [f"📍 Acuan {tgl_id(S['tgl_acuan'])}"])

    st.markdown('<div class="sec">1. Item pekerjaan</div>', unsafe_allow_html=True)
    st.caption("Isi baris yang diperlukan. Klik baris kosong paling bawah untuk menambah, "
               "pilih baris lalu tekan Delete untuk menghapus. Total bobot idealnya 100%.")
    edited = st.data_editor(
        S["data_pekerjaan"], num_rows="dynamic", width="stretch", key="editor_items",
        column_config={
            COL_NAMA: st.column_config.TextColumn(COL_NAMA),
            COL_BOBOT: st.column_config.NumberColumn(COL_BOBOT, min_value=0.0, max_value=100.0, step=0.5),
            COL_MULAI: st.column_config.NumberColumn(COL_MULAI, min_value=1, step=1, format="%d"),
            COL_DURASI: st.column_config.NumberColumn(COL_DURASI, min_value=1, step=1, format="%d"),
            COL_REAL: st.column_config.NumberColumn(COL_REAL, min_value=0.0, max_value=100.0, step=1.0),
        },
    )
    S["data_pekerjaan"] = edited
    items = clean_items(edited)
    total_bobot = float(items[COL_BOBOT].sum()) if len(items) else 0.0
    if len(items) and abs(total_bobot - 100) > 0.01:
        st.warning(f"Total bobot saat ini {total_bobot:.1f}%. Perhitungan dinormalisasi ke 100%.")

    st.markdown('<div class="sec">2. Riwayat realisasi kumulatif (opsional)</div>', unsafe_allow_html=True)
    st.caption("Dipakai untuk menggambar garis realisasi. Isi hari ke berapa dan progres kumulatif seluruh proyek saat itu.")
    S["riwayat"] = st.data_editor(
        S["riwayat"], num_rows="dynamic", width="stretch", key="editor_riwayat",
        column_config={
            COL_HARI: st.column_config.NumberColumn(COL_HARI, min_value=0, step=1, format="%d"),
            COL_RKUM: st.column_config.NumberColumn(COL_RKUM, min_value=0.0, max_value=100.0, step=0.5),
        },
    )

    total = int(S["durasi_total"] or 0)
    if total <= 0:
        empty_state("⏱️", "Durasi kontrak belum diisi", "Isi durasi kontrak (hari) di Pengaturan proyek pada panel kiri.")
        return
    if len(items) == 0 or total_bobot <= 0:
        empty_state("🧱", "Belum ada item pekerjaan", "Isi minimal satu item dengan bobot, hari mulai, dan durasi pada tabel di atas.")
        return

    days, plan = planned_curve(items, total)
    hari = hari_acuan()
    target = float(np.interp(hari, days, plan))
    real = actual_total(items)
    riwayat = clean_riwayat(S["riwayat"])

    st.markdown('<div class="sec">3. Kurva S</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=plan, name="Rencana", line=dict(color=BLUEPRINT, width=3),
                             fill="tozeroy", fillcolor="rgba(29,78,137,0.08)"))
    if len(riwayat) > 0:
        fig.add_trace(go.Scatter(x=riwayat[COL_HARI], y=riwayat[COL_RKUM], name="Realisasi (riwayat)",
                                 mode="lines+markers", line=dict(color=ACTUAL, width=3), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=[hari], y=[real], name="Realisasi saat ini (dari item)", mode="markers",
                             marker=dict(size=16, color=INK, symbol="star")))
    fig.add_vline(x=hari, line_dash="dash", line_color="#94A3B8", annotation_text="Hari acuan")
    fig.update_layout(xaxis_title="Hari ke", yaxis_title="Progres kumulatif (%)", yaxis_range=[0, 100])
    style_fig(fig, 440)
    st.plotly_chart(fig, width="stretch")

    strip([
        ("Hari acuan", f"ke-{hari}", "", f"dari {total} hari"),
        ("Target (rencana)", fmt(target), "%", "Dari Kurva S rencana"),
        ("Realisasi (dari item)", fmt(real), "%", f"Deviasi {real - target:+.1f} poin".replace(".", ",")),
    ])

    st.markdown('<div class="sec">4. Status per item pekerjaan</div>', unsafe_allow_html=True)
    detail = tabel_per_item(items, hari)
    tampil = detail.copy()
    tampil["Status"] = tampil["Status"].map(lambda s: f"{ITEM_ICON[s]} {s}")
    st.dataframe(
        tampil, width="stretch", hide_index=True,
        column_config={
            "Rencana saat ini (%)": st.column_config.ProgressColumn("Rencana saat ini (%)", min_value=0, max_value=100, format="%.1f"),
            COL_REAL: st.column_config.ProgressColumn(COL_REAL, min_value=0, max_value=100, format="%.1f"),
        },
    )
    bar = go.Figure()
    bar.add_bar(x=detail[COL_NAMA], y=detail["Rencana saat ini (%)"], name="Rencana", marker_color=BLUEPRINT)
    bar.add_bar(x=detail[COL_NAMA], y=detail[COL_REAL], name="Realisasi", marker_color=ACTUAL)
    bar.update_layout(barmode="group", yaxis_title="Progres item (%)", yaxis_range=[0, 100])
    style_fig(bar, 380)
    st.plotly_chart(bar, width="stretch")


def page_export():
    hero("Export laporan", "Unduh hasil analisis risiko untuk dibagikan ke manajemen atau klien")
    m = get_metrics()
    if not m["ready"]:
        empty_state("📄", "Belum ada data untuk dilaporkan",
                    "Isi data di Dashboard Utama (mode manual) atau Detail Kurva S (mode otomatis), lalu kembali ke sini.")
        return

    gaya = STATUS_STYLE[m["status"]]
    st.markdown(
        f'<div class="banner" style="background-color:{gaya["color"]}"><div class="big">{gaya["icon"]}</div>'
        f'<div><div class="t">{gaya["judul"]}</div>'
        f'<div class="s">Target {m["target"]:.1f}%, realisasi {m["real"]:.1f}%, sisa waktu {m["sisa"]} hari.</div></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="card"><div class="h">Rekomendasi</div><p>{rekomendasi(m)}</p></div>', unsafe_allow_html=True)

    nama_file = "".join(ch if ch.isalnum() else "_" for ch in m["nama"]) or "proyek"
    tgl = datetime.now().strftime("%Y%m%d")
    c1, c2 = st.columns(2)
    try:
        c1.download_button("⬇️  Download PDF", data=build_pdf(m), file_name=f"laporan_{nama_file}_{tgl}.pdf",
                           mime="application/pdf", width="stretch")
    except Exception as e:
        c1.error(f"Gagal membuat PDF: {e}")
    try:
        c2.download_button("⬇️  Download Excel", data=build_excel(m), file_name=f"laporan_{nama_file}_{tgl}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    except Exception as e:
        c2.error(f"Gagal membuat Excel: {e}")


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    halaman = sidebar()
    if halaman == "dashboard":
        page_dashboard()
    elif halaman == "kurva":
        page_kurva_s()
    else:
        page_export()


main()
