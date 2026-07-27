"""Uji fungsi murni `lux_ltf/ingest.py`.

Tidak ada uji yang menyentuh jaringan. Yang diuji adalah aritmetika bulan,
bentuk URL, parsing arsip, verifikasi checksum, dan audit integritas — yakni
bagian yang dapat salah tanpa terlihat.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from lux_ltf import ingest


# ---------------------------------------------------------------- tetapan


def test_interval_dan_menit_sepadan():
    assert set(ingest.INTERVAL) == set(ingest.MENIT_PER_INTERVAL)
    assert ingest.MENIT_PER_INTERVAL == {"5m": 5, "15m": 15}


def test_simbol_probe_dua_belas_dan_unik():
    assert len(ingest.SIMBOL_PROBE) == 12
    assert len(set(ingest.SIMBOL_PROBE)) == 12
    assert ingest.BATAS_SIMBOL_TANPA_IZIN == 12


# ---------------------------------------------------------------- bulan


def test_bulan_berurut_78_bulan():
    bulan = ingest.bulan_berurut((2020, 1), (2026, 6))
    assert len(bulan) == 78
    assert bulan[0] == (2020, 1)
    assert bulan[-1] == (2026, 6)


def test_bulan_berurut_lintas_tahun():
    assert ingest.bulan_berurut((2020, 11), (2021, 2)) == [
        (2020, 11),
        (2020, 12),
        (2021, 1),
        (2021, 2),
    ]


def test_bulan_berurut_satu_bulan():
    assert ingest.bulan_berurut((2024, 5), (2024, 5)) == [(2024, 5)]


def test_bulan_berurut_terbalik_ditolak():
    with pytest.raises(ValueError):
        ingest.bulan_berurut((2026, 6), (2020, 1))


# ---------------------------------------------------------------- nama & url


def test_nama_arsip_berbantalan_nol():
    assert ingest.nama_arsip("BTCUSDT", "5m", 2020, 3) == "BTCUSDT-5m-2020-03.zip"


def test_url_arsip_dan_checksum():
    u = ingest.url_arsip("ETHUSDT", "15m", 2025, 12)
    assert u == (
        "https://data.binance.vision/data/futures/um/monthly/klines/"
        "ETHUSDT/15m/ETHUSDT-15m-2025-12.zip"
    )
    assert ingest.url_checksum("ETHUSDT", "15m", 2025, 12) == u + ".CHECKSUM"


# ---------------------------------------------------------------- bar diharapkan


@pytest.mark.parametrize(
    "tahun,bulan,interval,harap",
    [
        (2021, 1, "5m", 31 * 288),
        (2021, 4, "5m", 30 * 288),
        (2020, 2, "5m", 29 * 288),  # kabisat
        (2021, 2, "5m", 28 * 288),
        (2020, 2, "15m", 29 * 96),
        (2026, 6, "15m", 30 * 96),
    ],
)
def test_bar_diharapkan(tahun, bulan, interval, harap):
    assert ingest.bar_diharapkan(tahun, bulan, interval) == harap


def test_bar_diharapkan_interval_asing_ditolak():
    with pytest.raises(ValueError):
        ingest.bar_diharapkan(2024, 1, "1h")


# ---------------------------------------------------------------- checksum


def test_sha256_hex_nilai_dikenal():
    assert ingest.sha256_hex(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_checksum_dari_teks_bentuk_binance():
    h = hashlib.sha256(b"data").hexdigest()
    teks = f"{h}  BTCUSDT-5m-2024-01.zip\n"
    assert ingest.checksum_dari_teks(teks) == h


def test_checksum_dari_teks_huruf_besar_dinormalkan():
    h = hashlib.sha256(b"data").hexdigest()
    assert ingest.checksum_dari_teks(h.upper() + "  x.zip") == h


@pytest.mark.parametrize("buruk", ["", "   ", "bukanhash  x.zip", "abc123  x.zip"])
def test_checksum_dari_teks_menolak_yang_tidak_sah(buruk):
    with pytest.raises(ValueError):
        ingest.checksum_dari_teks(buruk)


# ---------------------------------------------------------------- parsing zip


def _zip_dari_baris(baris, nama="data.csv"):
    kantong = io.BytesIO()
    with zipfile.ZipFile(kantong, "w") as arsip:
        arsip.writestr(nama, "\n".join(",".join(str(x) for x in b) for b in baris))
    return kantong.getvalue()


def _baris_klines(ts, harga=100.0):
    return [ts, harga, harga + 1, harga - 1, harga + 0.5, 10.0,
            ts + 1, 0, 0, 0, 0, 0]


TAJUK = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_volume", "taker_buy_quote_volume", "ignore",
]


def test_baris_dari_zip_tanpa_tajuk():
    isi = _zip_dari_baris([_baris_klines(0), _baris_klines(300000)])
    assert len(ingest.baris_dari_zip(isi)) == 2


def test_baris_dari_zip_membuang_tajuk():
    isi = _zip_dari_baris([TAJUK, _baris_klines(0), _baris_klines(300000)])
    baris = ingest.baris_dari_zip(isi)
    assert len(baris) == 2
    assert baris[0][0] == "0"


def test_baris_dari_zip_menolak_dua_csv():
    kantong = io.BytesIO()
    with zipfile.ZipFile(kantong, "w") as arsip:
        arsip.writestr("a.csv", "1,2")
        arsip.writestr("b.csv", "3,4")
    with pytest.raises(ValueError):
        ingest.baris_dari_zip(kantong.getvalue())


# ---------------------------------------------------------------- ke_lilin


def test_ke_lilin_enam_medan():
    baris = [[str(x) for x in _baris_klines(1600000000000)]]
    lilin = ingest.ke_lilin(baris)
    assert len(lilin) == 1
    assert len(lilin[0]) == 6
    ts, o, h, l, c, v = lilin[0]
    assert ts == 1600000000000
    assert (o, h, l, c, v) == (100.0, 101.0, 99.0, 100.5, 10.0)


def test_ke_lilin_mikrodetik_diturunkan_ke_milidetik():
    baris = [[str(x) for x in _baris_klines(1600000000000000)]]
    assert ingest.ke_lilin(baris)[0][0] == 1600000000000


def test_ke_lilin_menolak_kolom_kurang():
    with pytest.raises(ValueError):
        ingest.ke_lilin([["1", "2", "3"]])


# ---------------------------------------------------------------- integritas


def test_periksa_urutan_bersih():
    langkah = 5 * 60_000
    ts = [i * langkah for i in range(10)]
    monoton, hilang, duplikat = ingest.periksa_urutan(ts, "5m")
    assert (monoton, hilang, duplikat) == (True, 0, 0)


def test_periksa_urutan_menemukan_celah():
    langkah = 5 * 60_000
    ts = [0, langkah, langkah * 4]  # dua bar hilang
    monoton, hilang, duplikat = ingest.periksa_urutan(ts, "5m")
    assert monoton is True
    assert hilang == 2
    assert duplikat == 0


def test_periksa_urutan_menemukan_duplikat():
    langkah = 15 * 60_000
    ts = [0, langkah, langkah, langkah * 2]
    monoton, hilang, duplikat = ingest.periksa_urutan(ts, "15m")
    assert (monoton, hilang, duplikat) == (True, 0, 1)


def test_periksa_urutan_menemukan_mundur():
    langkah = 5 * 60_000
    ts = [langkah * 2, langkah]
    monoton, _, _ = ingest.periksa_urutan(ts, "5m")
    assert monoton is False


def test_periksa_urutan_satu_bar_aman():
    assert ingest.periksa_urutan([0], "5m") == (True, 0, 0)


# ---------------------------------------------------------------- ringkas


def test_ringkas_menjumlahkan_dan_menghitung_status():
    catatan = [
        {"status": "ok", "byte_zip": 100, "byte_parquet": 40, "bar": 288,
         "bar_hilang": 1, "bar_duplikat": 0, "checksum": "cocok",
         "monoton_naik": True},
        {"status": "ok", "byte_zip": 200, "byte_parquet": 80, "bar": 288,
         "bar_hilang": 0, "bar_duplikat": 2, "checksum": "tidak_ada",
         "monoton_naik": False},
        {"status": "tidak_ada"},
    ]
    r = ingest.ringkas(catatan)
    assert r["cacah_unit"] == 3
    assert r["per_status"] == {"ok": 2, "tidak_ada": 1}
    assert r["total_byte_zip"] == 300
    assert r["total_byte_parquet"] == 120
    assert r["total_bar"] == 576
    assert r["total_bar_hilang"] == 1
    assert r["total_bar_duplikat"] == 2
    assert r["checksum_tidak_ada"] == 1
    assert r["checksum_beda"] == 0
    assert r["berkas_tak_monoton"] == 1


# ---------------------------------------------------------------- pagar CLI


def test_pagar_menolak_lebih_dari_dua_belas_simbol():
    simbol = [f"S{i}USDT" for i in range(13)]
    kode = ingest.main(["--simbol", *simbol])
    assert kode == 2


def test_pagar_menolak_interval_asing():
    kode = ingest.main(["--interval", "1h"])
    assert kode == 2


def test_pagar_menolak_bulan_tak_sah():
    assert ingest.main(["--bulan-awal", "2020"]) == 2


def test_pagar_menolak_bulan_terbalik():
    assert ingest.main(["--bulan-awal", "2026-06", "--bulan-akhir", "2020-01"]) == 2


def test_urai_bulan():
    assert ingest.urai_bulan("2026-06") == (2026, 6)
    with pytest.raises(ValueError):
        ingest.urai_bulan("2026/06")
