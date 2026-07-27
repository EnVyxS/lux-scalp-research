"""Gerbang kesetiaan angkatan.

Uji ini tidak memeriksa perilaku detektor. Ia memeriksa satu hal yang lebih
mendasar: bahwa berkas yang mengaku salinan `bot_v8` benar-benar salinan byte
demi byte. Angkatan yang tidak setia membuat seluruh hasil uji berbicara
tentang kode yang salah.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from lux_ltf.sinyal import sumber

HEKS = set("0123456789abcdef")


# ------------------------------------------------------------------ provenans


def test_empat_berkas_sumber_terekam():
    assert set(sumber.SUMBER) == {
        "patterns.py",
        "strategy.py",
        "risk.py",
        "config.py",
    }


@pytest.mark.parametrize("nama", sorted(sumber.SUMBER))
def test_bentuk_provenans(nama):
    catatan = sumber.SUMBER[nama]
    assert isinstance(catatan["byte"], int) and catatan["byte"] > 0
    assert isinstance(catatan["baris"], int) and catatan["baris"] > 0
    sha = catatan["sha256"]
    blob = catatan["blob"]
    assert len(sha) == 64 and set(sha) <= HEKS, nama
    assert len(blob) == 40 and set(blob) <= HEKS, nama
    assert str(catatan["catatan"]).strip()


def test_hash_sumber_tidak_bertabrakan():
    sha = [c["sha256"] for c in sumber.SUMBER.values()]
    blob = [c["blob"] for c in sumber.SUMBER.values()]
    assert len(set(sha)) == len(sha)
    assert len(set(blob)) == len(blob)


def test_ukuran_patterns_bukan_ukuran_known_issues():
    # Koreksi eksplisit atas kesalahan catatan lama: 32.886 B adalah ukuran
    # KNOWN_ISSUES.md, bukan patterns.py. Uji ini mencegahnya kembali.
    assert sumber.SUMBER["patterns.py"]["byte"] == 31887
    assert sumber.SUMBER["patterns.py"]["byte"] != 32886


# ------------------------------------------------------------------ perkakas


def test_blob_git_cocok_dengan_definisi_git():
    isi = b"halo\n"
    harap = hashlib.sha1(b"blob 5\0" + isi).hexdigest()
    assert sumber.blob_git(isi) == harap


def test_blob_git_kosong_nilai_dikenal():
    # git hash-object atas berkas kosong.
    assert sumber.blob_git(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_sha256_isi_kosong():
    assert sumber.sha256_isi(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_periksa_berkas_menolak_isi_salah(tmp_path):
    palsu = tmp_path / "pola_v9.py"
    palsu.write_text("# bukan patterns.py\n", encoding="utf-8")
    temuan = sumber.periksa_berkas(palsu, "patterns.py")
    assert temuan["ada"] is True
    assert temuan["setia"] is False
    assert temuan["sha256"] != temuan["sha256_harap"]


def test_periksa_berkas_absen(tmp_path):
    temuan = sumber.periksa_berkas(tmp_path / "tidak_ada.py", "patterns.py")
    assert temuan["ada"] is False
    assert temuan["setia"] is False


# ------------------------------------------------------------------ gerbang


def test_daftar_angkatan_menunjuk_ke_sumber_dikenal():
    for jalur, nama in sumber.BERKAS_DIANGKAT.items():
        assert nama in sumber.SUMBER
        assert jalur.startswith("lux_ltf/")
        assert jalur.endswith(".py")


def test_engine_sengaja_tidak_diangkat():
    assert "engine.py" in sumber.SENGAJA_TIDAK_DIANGKAT
    assert "engine.py" not in sumber.SUMBER
    assert all(n != "engine.py" for n in sumber.BERKAS_DIANGKAT.values())


@pytest.mark.parametrize("jalur", sorted(sumber.BERKAS_DIANGKAT))
def test_berkas_terangkat_setia_bila_ada(jalur):
    """Bila berkas terangkat sudah ada, ia WAJIB byte-identik.

    Selama berkas itu belum ada, uji ini lulus tanpa menghalangi — utangnya
    tercatat di `lux_ltf/sinyal/SUMBER.md` §5, bukan disembunyikan di sini.
    """
    berkas = Path(jalur)
    if not berkas.exists():
        pytest.skip(f"{jalur} belum diangkat (utang tercatat di SUMBER.md §5)")
    temuan = sumber.periksa_berkas(berkas, sumber.BERKAS_DIANGKAT[jalur])
    assert temuan["setia"], (
        f"{jalur} TIDAK byte-identik dengan {temuan['nama_sumber']}: "
        f"byte {temuan['byte']} vs {temuan['byte_harap']}, "
        f"blob {temuan['blob']} vs {temuan['blob_harap']}"
    )


def test_utang_angkatan_melaporkan_setiap_jalur():
    laporan = sumber.utang_angkatan()
    assert set(laporan) == set(sumber.BERKAS_DIANGKAT)
    for temuan in laporan.values():
        assert "setia" in temuan and "ada" in temuan
