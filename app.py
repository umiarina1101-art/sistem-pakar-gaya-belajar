import streamlit as st
import json
import time
import re
from collections import Counter

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="Sistem Pakar Gaya Belajar",
    page_icon=None,
    layout="wide",  # Tetap wide, tapi kita batasi lebarnya via CSS
    initial_sidebar_state="expanded"
)

# ==========================================
# PERBAIKAN PAKSA WARNA TEKS
# ==========================================
st.markdown("""
<style>
div[data-testid="stTabs"] p, 
...
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOAD CSS EKSTERNAL
# ==========================================
def load_css(file_name: str):
    with open(file_name, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

try:
    load_css("style.css")
except FileNotFoundError:
    st.warning("File `style.css` tidak ditemukan. Aplikasi berjalan tanpa styling.")

# ==========================================
# PERBAIKAN WARNA TEKS TAB (ANTI HILANG)
# ==========================================
st.markdown("""
<style>
/* Memperbaiki teks Tab yang tidak terlihat */
.stTabs [data-baseweb="tab-list"] button p {
    color: #475569 !important; /* Warna abu-abu gelap untuk tab tidak aktif */
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] p {
    color: #7c3aed !important; /* Warna ungu menyala untuk tab aktif */
    font-weight: 800 !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background-color: #7c3aed !important;
}

/* Memperbaiki teks di dalam tab (Daftar Fakta / Aturan) */
.stTabs [data-baseweb="tab-panel"] p, 
.stTabs [data-baseweb="tab-panel"] span,
.stTabs [data-baseweb="tab-panel"] div,
.stTabs [data-baseweb="tab-panel"] h4 {
    color: #1e293b !important; /* Paksa jadi gelap agar terbaca di background terang */
}

/* Memperbaiki kotak input search */
.stTextInput input {
    color: #1e293b !important;
    background-color: #ffffff !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. LOAD RULES
# ==========================================
@st.cache_data(show_spinner=False)
def load_rules(path: str = "rules.json"):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    data = json.loads(raw)
    for key in ("fakta", "aturan", "kesimpulan", "saran"):
        if key not in data:
            raise ValueError(f"Field '{key}' tidak ditemukan di rules.json")
    if not isinstance(data["fakta"], list) or not isinstance(data["aturan"], list):
        raise ValueError("Field 'fakta' dan 'aturan' harus berupa list")
    for f_ in data["fakta"]:
        if not {"id", "teks"}.issubset(f_.keys()):
            raise ValueError(f"Fakta tidak valid: {f_}")
    for r_ in data["aturan"]:
        if not {"kode", "premis", "operator", "kesimpulan"}.issubset(r_.keys()):
            raise ValueError(f"Aturan tidak valid: {r_}")
        if r_["operator"] not in ("AND", "OR"):
            raise ValueError(f"Operator tidak valid pada {r_['kode']}: {r_['operator']}")
    if "prioritas" not in data:
        data["prioritas"] = {}
    return data

try:
    data = load_rules()
except FileNotFoundError:
    st.error("File `rules.json` tidak ditemukan di folder aplikasi.")
    st.stop()
except json.JSONDecodeError as e:
    st.error(f"`rules.json` bukan JSON valid: {e}")
    st.stop()
except ValueError as e:
    st.error(f"Struktur `rules.json` tidak valid: {e}")
    st.stop()
except Exception as e:
    st.error(f"Gagal memuat basis pengetahuan: {e}")
    st.stop()

# ==========================================
# 4. MESIN INFERENSI (TIDAK DIUBAH)
# ==========================================
def forward_chaining_trace(fakta_terpilih, aturan):
    memori = set(fakta_terpilih)
    jejak = []
    iterasi_trace = []
    iterasi_trace.append({"iterasi": 0, "memori": sorted(memori), "aturan_aktif": [], "aturan_dipilih": "—", "fakta_baru": None})
    iter_num = 1
    while True:
        aturan_aktif = []
        for rule in aturan:
            if rule["kesimpulan"] in memori:
                continue
            premis = rule["premis"]
            op = rule["operator"]
            cocok = (all(p in memori for p in premis) if op == "AND" else any(p in memori for p in premis))
            if cocok:
                aturan_aktif.append(rule)
        if not aturan_aktif:
            iterasi_trace.append({"iterasi": iter_num, "memori": sorted(memori), "aturan_aktif": [], "aturan_dipilih": "STOP", "fakta_baru": None})
            break
        rule_dipilih = aturan_aktif[0]
        memori.add(rule_dipilih["kesimpulan"])
        fakta_baru = rule_dipilih["kesimpulan"]
        op_str = f" {rule_dipilih['operator']} "
        jejak.append(f"Aturan **{rule_dipilih['kode']}**: {op_str.join(rule_dipilih['premis'])} → {fakta_baru}")
        iterasi_trace.append({"iterasi": iter_num, "memori": sorted(memori), "aturan_aktif": [r["kode"] for r in aturan_aktif], "aturan_dipilih": rule_dipilih["kode"], "fakta_baru": fakta_baru})
        iter_num += 1
    return memori, jejak, iterasi_trace


def pilih_hasil(memori, prioritas):
    def score(h):
        jenis = 1 if h.startswith("H") else 0
        angka = int(re.sub(r"\D", "", h) or 0)
        return (jenis, prioritas.get(h, 0), angka)
    kandidat = [k for k in memori if re.fullmatch(r"[HK]\d+", k)]
    if not kandidat:
        return ""
    kandidat.sort(key=score, reverse=True)
    return kandidat[0]


def hitung_skor_kategori(fakta_terpilih, data_fakta):
    kat_map = {f["id"]: f.get("kategori", "") for f in data_fakta}
    counter = Counter(kat_map.get(fid, "") for fid in fakta_terpilih)
    counter.pop("", None)
    total = sum(counter.values()) or 1
    return {k: int(v / total * 100) for k, v in counter.items()}, counter


# ==========================================
# 5. SESSION STATE
# ==========================================
DEFAULTS = {
    "halaman": "welcome",
    "konsultasi_selesai": False,
    "memori_kerja": [],
    "jejak": [],
    "iterasi_trace": [],
    "hasil_terpilih": "",
    "skor_kategori": {},
    "fakta_terpilih_final": [],
    "reset_confirm": False,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset_konsultasi():
    st.session_state.konsultasi_selesai = False
    st.session_state.memori_kerja = []
    st.session_state.jejak = []
    st.session_state.iterasi_trace = []
    st.session_state.hasil_terpilih = ""
    st.session_state.skor_kategori = {}
    st.session_state.fakta_terpilih_final = []
    st.session_state.reset_confirm = False


# ==========================================
# 6. SVG ICON HELPERS
# ==========================================
ICON_PATHS = {
    "home": '<path d="M3 12l9-9 9 9"/><path d="M5 10v10a1 1 0 001 1h3a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1h3a1 1 0 001-1V10"/>',
    "brain": '<path d="M9.5 2A2.5 2.5 0 0112 4.5v15a2.5 2.5 0 01-4.96.44 2.5 2.5 0 01-2.96-3.08 3 3 0 01-.34-5.58 2.5 2.5 0 011.32-4.24 2.5 2.5 0 014.44-1.54z"/><path d="M14.5 2A2.5 2.5 0 0012 4.5v15a2.5 2.5 0 004.96.44 2.5 2.5 0 002.96-3.08 3 3 0 00.34-5.58 2.5 2.5 0 00-1.32-4.24 2.5 2.5 0 00-4.44-1.54z"/>',
    "book": '<path d="M4 4h7a3 3 0 013 3v13a2 2 0 00-2-2H4V4z"/><path d="M20 4h-7a3 3 0 00-3 3v13a2 2 0 012-2h8V4z"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    "headphones": '<path d="M4 14v-2a8 8 0 0116 0v2"/><rect x="3" y="14" width="4" height="6" rx="1"/><rect x="17" y="14" width="4" height="6" rx="1"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 15l4-4 4 4 5-5"/>',
    "refresh": '<path d="M23 4v6h-6M1 20v-6h6"/><path d="M3.5 9a9 9 0 0114.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0020.5 15"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
    "download": '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
    "check": '<path d="M20 6L9 17l-5-5"/>',
    "lightbulb": '<path d="M9 18h6M10 22h4M12 2a7 7 0 00-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0012 2z"/>',
    "graduation": '<path d="M22 10L12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1.5 2.5 3 6 3s6-1.5 6-3v-5"/>',
}

def svg(name, size=20, color="currentColor", stroke_width=2):
    path = ICON_PATHS.get(name, "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )


# ==========================================
# 7. SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown(
        f'<div class="sidebar-brand">{svg("graduation", 26, "#ffffff")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-title">Sistem Pakar</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Gaya Belajar VAK</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-nav-label">Navigasi</div>', unsafe_allow_html=True)

    nav_items = [
        ("home", "welcome", "Beranda"),
        ("konsul", "konsultasi", "Konsultasi"),
        ("basis", "basis", "Basis Pengetahuan"),
        ("panduan", "panduan", "Panduan"),
    ]
    for key, page, label in nav_items:
        if st.button(
            label,
            use_container_width=True,
            key=f"nav_{key}",
            type="primary" if st.session_state.halaman == page else "secondary",
        ):
            st.session_state.halaman = page
            st.rerun()

    st.markdown("---")
    st.caption("Dibuat untuk UTS Sistem Pakar")


# ==========================================
# 8. HALAMAN: WELCOME
# ==========================================
def render_welcome():
    st.markdown("""
    <div class="hero">
        <div class="hero-badge">Selamat Datang</div>
        <h1 class="hero-title">Sistem Pakar<br>Gaya Belajar</h1>
        <div class="hero-meta">
            <span>2 menit</span>
            <span>Akurat</span>
            <span>Berbasis aturan</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- CTA ATAS ---
    # Gunakan perbandingan kolom [1, 2, 1] agar tombol tidak terlalu lebar
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if st.button("Mulai Konsultasi", use_container_width=True, key="cta_mulai"):
            st.session_state.halaman = "konsultasi"
            reset_konsultasi()
            st.rerun()

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Kenali 3 Gaya Belajar</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Setiap orang punya cara belajar yang berbeda. Kenali gayamu.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        st.markdown(f"""
        <div class="vak-card vak-visual">
            <div class="vak-icon">{svg("eye", 22, "#2563eb")}</div>
            <div class="vak-tag">VISUAL</div>
            <h3>Belajar lewat Melihat</h3>
            <p>Gambar, diagram, warna, mind map, dan video lebih mudah diingat.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="vak-card vak-audio">
            <div class="vak-icon">{svg("headphones", 22, "#7c3aed")}</div>
            <div class="vak-tag">AUDITORI</div>
            <h3>Belajar lewat Mendengar</h3>
            <p>Diskusi, rekaman, podcast, dan penjelasan verbal paling efektif.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="vak-card vak-kines">
            <div class="vak-icon">{svg("activity", 22, "#059669")}</div>
            <div class="vak-tag">KINESTETIK</div>
            <h3>Belajar lewat Bergerak</h3>
            <p>Praktik langsung, role-play, dan pengalaman fisik lebih bermakna.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    st.markdown('<div class="section-title">Bagaimana Cara Kerjanya?</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-sub">Tiga langkah sederhana untuk menemukan gaya belajarmu.</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">1</div>
            <h4>Pilih Pernyataan</h4>
            <p>Centang pernyataan yang paling sesuai dengan kebiasaan belajarmu.</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">2</div>
            <h4>Sistem Menganalisis</h4>
            <p>Mesin inferensi memproses jawabanmu menggunakan forward chaining.</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="step-card">
            <div class="step-num">3</div>
            <h4>Dapatkan Hasil</h4>
            <p>Lihat gaya belajarmu, rekomendasi, dan penjelasan lengkap.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    # --- CTA BAWAH ---
    st.markdown("""
    <div class="cta-banner">
        <h3>Siap menemukan gaya belajarmu?</h3>
        <p>Hanya butuh 2 menit. Gratis, tanpa login.</p>
    </div>
    """, unsafe_allow_html=True)
    # Gunakan perbandingan kolom [1, 2, 1] di sini juga
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        if st.button("Mulai Sekarang", use_container_width=True, key="cta_mulai_2"):
            st.session_state.halaman = "konsultasi"
            reset_konsultasi()
            st.rerun()


# ==========================================
# 9. HALAMAN: KONSULTASI
# ==========================================
def render_konsultasi():
    if not st.session_state.konsultasi_selesai:
        st.markdown("""
        <div class="page-header">
            <h1>Temukan Gaya Belajarmu</h1>
            <p>Pilih pernyataan yang sesuai dengan dirimu. Sistem akan menganalisis secara otomatis.</p>
        </div>
        """, unsafe_allow_html=True)

        fakta_terpilih = []

        for fakta in data["fakta"]:
            label = f"**[{fakta['id']}]** {fakta['teks']}"
            with st.container(border=True):
                if st.checkbox(label, key=fakta["id"]):
                    fakta_terpilih.append(fakta["id"])

        n = len(fakta_terpilih)
        progress_val = min(n / 2, 1.0)
        status_txt = "Siap dianalisis" if n >= 2 else "minimal 2"
        st.markdown(
            '<div class="counter-box">'
            '<span class="lbl">Pernyataan dipilih</span>'
            f'<span class="val">{n} / {len(data["fakta"])} &middot; {status_txt}</span>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.progress(progress_val)
        valid = n >= 2
        if not valid:
            st.caption("(Pilih minimal 2 pernyataan untuk mengaktifkan tombol)")

        if st.button("Analisis Sekarang", type="primary", use_container_width=True, disabled=not valid):
            placeholder = st.empty()
            placeholder.markdown(
                '<div style="background:#ffffff;border:1px solid #e2e8f0;'
                'border-radius:12px;padding:24px;margin:16px 0;">'
                '<div class="skeleton" style="width:40%;"></div>'
                '<div class="skeleton" style="width:70%;"></div>'
                '<div class="skeleton" style="width:55%;"></div>'
                '</div>',
                unsafe_allow_html=True,
            )
            time.sleep(1.0)
            memori, jejak, trace = forward_chaining_trace(fakta_terpilih, data["aturan"])
            hasil = pilih_hasil(memori, data.get("prioritas", {}))
            skor, _counter = hitung_skor_kategori(fakta_terpilih, data["fakta"])
            st.session_state.konsultasi_selesai = True
            st.session_state.memori_kerja = list(memori)
            st.session_state.jejak = jejak
            st.session_state.iterasi_trace = trace
            st.session_state.hasil_terpilih = hasil
            st.session_state.skor_kategori = skor
            st.session_state.fakta_terpilih_final = list(fakta_terpilih)
            placeholder.empty()
            st.rerun()

    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("""
            <div class="page-header">
                <h1>Analisis Selesai</h1>
                <p>Jelajahi hasil, trace iterasi, dan penjelasan inferensi di tab di bawah.</p>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.write("")
            if st.button("Konsultasi Ulang", use_container_width=True):
                st.session_state.reset_confirm = True

        if st.session_state.reset_confirm:
            st.warning("Yakin ingin mengulang konsultasi? Hasil saat ini akan hilang.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Ya, ulangi", use_container_width=True):
                    reset_konsultasi()
                    st.rerun()
            with c2:
                if st.button("Batal", use_container_width=True):
                    st.session_state.reset_confirm = False
                    st.rerun()

        st.write("")
        hasil_terpilih = st.session_state.hasil_terpilih
        skor = st.session_state.skor_kategori or {}

        tab1, tab2, tab3, tab4 = st.tabs([
            "Hasil & Rekomendasi", "Distribusi",
            "Trace Iterasi", "Jejak Inferensi",
        ])

        with tab1:
            if hasil_terpilih:
                st.markdown(
                    '<div class="result-panel">'
                    '<div class="result-label">Hasil Analisis Gaya Belajar</div>'
                    f'<div class="result-value">{data["kesimpulan"][hasil_terpilih]}</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="saran-card">'
                    '<h4>Rekomendasi Strategi Belajar</h4>'
                    f'<p>{data["saran"][hasil_terpilih]}</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                fakta_str = ", ".join([f for f in st.session_state.memori_kerja if f.startswith("F")])
                skor_text = "\n".join([f"  {k}: {v}%" for k, v in skor.items()]) if skor else "  (tidak ada)"
                teks_download = (
                    "HASIL ANALISIS SISTEM PAKAR GAYA BELAJAR\n"
                    "------------------------------------------\n"
                    f"Hasil Diagnosis : {data['kesimpulan'][hasil_terpilih]}\n"
                    f"Saran           : {data['saran'][hasil_terpilih]}\n\n"
                    "Distribusi Kecenderungan:\n"
                    f"{skor_text}\n\n"
                    "Fakta yang Dipilih:\n"
                    f"{fakta_str}\n\n"
                    "Aturan yang Dijalankan:\n"
                    + "\n".join(st.session_state.jejak) + "\n"
                )
                st.download_button(
                    label="Unduh Hasil Analisis (.txt)",
                    data=teks_download,
                    file_name="Hasil_Gaya_Belajar.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            else:
                st.markdown(
                    '<div class="result-panel">'
                    '<div class="result-label">Status Analisis</div>'
                    '<div class="result-value" style="color:#fca5a5;">Belum Dapat Disimpulkan</div>'
                    '<div class="result-desc">Fakta yang dipilih belum cukup. Silakan tambah pernyataan.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

        with tab2:
            st.markdown("#### Distribusi Kecenderungan")
            if skor:
                for kat, label, color in [
                    ("V", "Visual", "#2563eb"),
                    ("A", "Auditori", "#7c3aed"),
                    ("K", "Kinestetik", "#059669"),
                ]:
                    pct = skor.get(kat, 0)
                    st.markdown(
                        '<div class="score-row">'
                        f'<div class="score-label">{label}</div>'
                        '<div class="score-bar-bg">'
                        f'<div class="score-bar-fill" style="width:{pct}%; background:{color};"></div>'
                        '</div>'
                        f'<div class="score-pct">{pct}%</div>'
                        '</div>',
                        unsafe_allow_html=True,
                    )
                st.write("")
                kategori_terkuat = max(skor, key=skor.get) if skor else None
                if kategori_terkuat:
                    nama = {"V": "Visual", "A": "Auditori", "K": "Kinestetik"}.get(kategori_terkuat, kategori_terkuat)
                    st.success(f"Kecenderungan dominan kamu: **{nama}** ({skor[kategori_terkuat]}%)")
            else:
                st.info("Belum ada data distribusi.")

        with tab3:
            st.caption("Tabel setiap iterasi mesin inferensi.")
            trace = st.session_state.iterasi_trace
            if not trace:
                st.info("Tidak ada iterasi tercatat.")
            else:
                rows_html = []
                for step in trace:
                    memori_str = ", ".join(step["memori"]) if step["memori"] else "—"
                    aktif_str = ", ".join(step["aturan_aktif"]) if step["aturan_aktif"] else "—"
                    dipilih = step["aturan_dipilih"]
                    if dipilih == "STOP":
                        dipilih_html = '<span class="trace-stop">STOP</span>'
                    else:
                        dipilih_html = f'<b style="color:#4338ca;">{dipilih}</b>'
                    fb = step["fakta_baru"]
                    fb_html = f'<span class="trace-new-fact">{fb}</span>' if fb else "—"
                    iter_badge = f'<span class="trace-iter-badge">{step["iterasi"]}</span>'
                    rows_html.append(
                        "<tr>"
                        f"<td>{iter_badge}</td><td>{memori_str}</td>"
                        f"<td>{aktif_str}</td><td>{dipilih_html}</td><td>{fb_html}</td>"
                        "</tr>"
                    )
                st.markdown(
                    '<table class="trace-table">'
                    "<thead><tr><th>Iterasi</th><th>Memori Kerja</th><th>Aturan Aktif</th>"
                    "<th>Aturan Dipilih</th><th>Fakta Baru</th></tr></thead>"
                    "<tbody>" + "".join(rows_html) + "</tbody></table>",
                    unsafe_allow_html=True,
                )

        with tab4:
            st.markdown("**Fakta Awal yang Dipilih:**")
            awal = ", ".join([f for f in st.session_state.memori_kerja if f.startswith("F")])
            st.info(awal if awal else "(tidak ada)")
            st.markdown("**Aturan Produksi yang Dijalankan:**")
            if not st.session_state.jejak:
                st.write("Tidak ada aturan yang cocok.")
            else:
                for j in st.session_state.jejak:
                    st.markdown(f"- {j}")


# ==========================================
# 10. HALAMAN: BASIS PENGETAHUAN
# ==========================================
def render_basis():
    st.markdown("""
    <div class="page-header">
        <h1>Basis Pengetahuan</h1>
        <p>Daftar Fakta (F) dan Aturan Produksi (R) yang digunakan oleh mesin inferensi.</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["Daftar Fakta", "Aturan Produksi (Rules)"])

    with tab1:
        q = st.text_input("Cari fakta (ID atau kata kunci):", "")
        st.write(f"Total: **{len(data['fakta'])}** fakta")
        filtered = [f for f in data["fakta"] if not q or q.lower() in f["id"].lower() or q.lower() in f["teks"].lower()]
        if not filtered:
            st.info("Tidak ada fakta yang cocok.")
        for f in filtered:
            st.markdown(f"**[{f['id']}]** {f['teks']}")

    with tab2:
        q = st.text_input("Cari aturan (kode atau fakta):", "")
        st.write(f"Total: **{len(data['aturan'])}** aturan")
        filtered = [
            r for r in data["aturan"]
            if not q or q.lower() in r["kode"].lower()
            or any(q.lower() in p.lower() for p in r["premis"])
            or q.lower() in r["kesimpulan"].lower()
        ]
        if not filtered:
            st.info("Tidak ada aturan yang cocok.")
        for r in filtered:
            premis_str = f' {r["operator"]} '.join(r["premis"])
            st.markdown(f'<div class="rule-box">IF {premis_str} THEN {r["kesimpulan"]}</div>', unsafe_allow_html=True)


# ==========================================
# 11. HALAMAN: PANDUAN
# ==========================================
def render_panduan():
    st.markdown("""
    <div class="page-header">
        <h1>Panduan Penggunaan</h1>
        <p>Cara kerja Sistem Pakar Gaya Belajar.</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("""
    **1. Beranda** — Halaman awal berisi penjelasan singkat tentang aplikasi.

    **2. Konsultasi** — Pilih minimal 2 pernyataan yang sesuai dengan kebiasaan belajarmu,
    lalu klik tombol **Analisis Sekarang**.

    **3. Hasil** — Setelah analisis selesai, kamu akan melihat:
    - Hasil gaya belajar + rekomendasi
    - Distribusi kecenderungan
    - Trace iterasi forward chaining
    - Jejak inferensi (aturan yang dijalankan)

    **4. Unduh** — Kamu bisa mengunduh hasil analisis dalam format .txt.
    """)


# ==========================================
# 12. ROUTER
# ==========================================
if st.session_state.halaman == "welcome":
    render_welcome()
elif st.session_state.halaman == "konsultasi":
    render_konsultasi()
elif st.session_state.halaman == "basis":
    render_basis()
elif st.session_state.halaman == "panduan":
    render_panduan()


# ==========================================
# 13. FOOTER
# ==========================================
st.markdown(
    '<div class="footer">Sistem Pakar Gaya Belajar VAK &middot; v2.0 &middot; UTS Sistem Pakar</div>',
    unsafe_allow_html=True,
)
