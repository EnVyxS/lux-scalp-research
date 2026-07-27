"""Pagar cacat 24 — "cache tanpa manifes".

Keempat run pertama repo ini merah bukan karena uji gagal, melainkan karena
`actions/setup-python@v5` dengan `cache: 'pip'` mencari `**/requirements.txt`
atau `**/pyproject.toml`, tidak menemukan apa pun, lalu mematikan langkah itu.
Durasi 6-18 detik adalah buktinya: terlalu pendek untuk `pip install` lima
paket, apalagi untuk pytest.

Uji di berkas ini menegakkan invarian: **setiap** alur kerja yang memakai
`cache: 'pip'` harus disertai berkas dependensi di akar repo. Ia memakai jalur
relatif terhadap berkas uji ini, bukan direktori kerja, supaya tidak bergantung
pada dari mana pytest dipanggil.
"""

from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
DIR_ALUR = AKAR / ".github" / "workflows"
POLA_CACHE = "cache: 'pip'"
# Pola yang benar-benar dicari oleh actions/setup-python untuk kunci cache pip.
BERKAS_DEPENDENSI = ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg")
PAKET_INTI = ("pandas", "pyarrow", "pyyaml", "pytest")


def _alur():
    if not DIR_ALUR.is_dir():
        return []
    return sorted(DIR_ALUR.glob("*.yml")) + sorted(DIR_ALUR.glob("*.yaml"))


def test_dir_alur_ada():
    assert DIR_ALUR.is_dir(), f"direktori alur kerja tidak ada: {DIR_ALUR}"


def test_ada_berkas_dependensi_di_akar():
    ada = [n for n in BERKAS_DEPENDENSI if (AKAR / n).is_file()]
    assert ada, (
        "tidak ada berkas dependensi di akar repo; setup-python dengan "
        f"cache: 'pip' akan gagal. Dicari: {BERKAS_DEPENDENSI}"
    )


def test_setiap_alur_dengan_cache_pip_punya_manifes():
    ada = [n for n in BERKAS_DEPENDENSI if (AKAR / n).is_file()]
    pemakai = []
    for jalur in _alur():
        if POLA_CACHE in jalur.read_text(encoding="utf-8"):
            pemakai.append(jalur.name)
    if pemakai:
        assert ada, (
            f"alur {pemakai} memakai {POLA_CACHE} tetapi akar repo tidak "
            "memuat berkas dependensi apa pun"
        )


def test_requirements_ada_dan_tidak_kosong():
    jalur = AKAR / "requirements.txt"
    assert jalur.is_file(), "requirements.txt harus ada di akar repo"
    isi = jalur.read_text(encoding="utf-8").strip()
    assert isi, "requirements.txt tidak boleh kosong"


def test_requirements_menyebut_paket_inti():
    isi = (AKAR / "requirements.txt").read_text(encoding="utf-8").lower()
    kurang = [p for p in PAKET_INTI if p not in isi]
    assert not kurang, f"paket inti tidak tercatat di requirements.txt: {kurang}"


def test_setiap_baris_requirements_dipatok():
    baris = (AKAR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    tak_dipatok = []
    for b in baris:
        b = b.strip()
        if not b or b.startswith("#"):
            continue
        if "==" not in b:
            tak_dipatok.append(b)
    assert not tak_dipatok, (
        "versi wajib dipatok supaya run dapat direproduksi: " f"{tak_dipatok}"
    )


def test_kedua_alur_hadir():
    nama = {j.name for j in _alur()}
    for wajib in ("tests.yml", "probe_ltf.yml"):
        assert wajib in nama, f"alur {wajib} hilang; ada: {sorted(nama)}"
