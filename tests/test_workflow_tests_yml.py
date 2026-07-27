"""Uji pagar untuk `.github/workflows/tests.yml`.

Mencerminkan pagar `lux-research`. Yang dijaga bukan gaya, melainkan sifat yang
kalau hilang membuat satu putaran CI tidak lagi cukup untuk mengetahui apa yang
terjadi:

1. cacah butir terkumpul tercetak walaupun pytest merah;
2. baris FAILED/ERROR tidak terpotong;
3. laporan dikomit **sebelum** hasil ditegakkan;
4. komit laporan memakai `[skip ci]` sehingga tidak memicu putaran berikutnya.
"""

from __future__ import annotations

from pathlib import Path

import pytest

JALUR = Path(".github/workflows/tests.yml")


@pytest.fixture(scope="module")
def isi() -> str:
    assert JALUR.exists(), f"{JALUR} tidak ada"
    return JALUR.read_text(encoding="utf-8")


def test_workflow_ada(isi):
    assert isi.strip()


def test_collect_only_hadir(isi):
    assert "--collect-only" in isi


def test_medan_butir_terkumpul(isi):
    assert "Butir terkumpul" in isi


def test_cacah_sebelum_pytest(isi):
    kumpul = isi.index("--collect-only")
    jalankan = isi.index("Jalankan pytest")
    assert kumpul < jalankan, "cacah butir harus berjalan sebelum pytest"


def test_ringkasan_kegagalan_pendek(isi):
    assert "-rf" in isi


def test_tb_short_dipertahankan(isi):
    assert "--tb=short" in isi
    assert "--tb=long" not in isi


def test_baris_failed_tidak_dipotong(isi):
    assert "grep -E '^(FAILED|ERROR)'" in isi


def test_ekor_dua_ratus(isi):
    assert "tail -n 200" in isi
    assert "tail -n 80" not in isi


def test_komit_sebelum_penegakan(isi):
    komit = isi.index("Komit laporan")
    tegak = isi.index("Tegakkan hasil")
    assert komit < tegak, "laporan harus dikomit sebelum hasil ditegakkan"


def test_skip_ci_hadir(isi):
    assert "[skip ci]" in isi


def test_pull_rebase_autostash(isi):
    assert "git pull --rebase --autostash" in isi


def test_pengaman_kode_keluar_utuh(isi):
    assert "set +e" in isi
    assert "kode=$?" in isi
    assert 'if [ "${KODE}" != "0" ]' in isi
    assert "exit 1" in isi


def test_cache_pip_sudah_ada_dan_tunggal(isi):
    assert isi.count("cache: 'pip'") == 1


def test_tidak_memakai_xdist_atau_x(isi):
    assert "xdist" not in isi
    assert " -x " not in isi


def test_pemicu_tidak_menyertakan_decisions_atau_journal(isi):
    kepala = isi.split("jobs:", 1)[0]
    assert "decisions/**" not in kepala
    assert "journal/**" not in kepala
    assert "lux_ltf/**" in kepala
    assert "tests/**" in kepala
