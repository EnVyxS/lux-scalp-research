"""Probe ketersediaan arsip klines Binance Futures UM untuk interval 5m dan 15m.

Apa yang dilakukan berkas ini
-----------------------------
Mengirim permintaan HEAD ke arsip bulanan Binance Vision dan mencatat kode HTTP
serta Content-Length. Ia **tidak** mengunduh isi berkas dan **tidak** menyentuh
harga sama sekali.

Apa yang TIDAK dilakukan
------------------------
Ia bukan backtest, bukan pra-saring strategi, dan tidak menghasilkan bukti
tentang tepi apa pun. Keluarannya selalu memuat ``"bukan_bukti": true``.
Satu-satunya pertanyaan yang dijawabnya: apakah data yang kita rencanakan
unduh benar-benar ada, untuk simbol mana, dan sebesar apa.

Kode keluar
-----------
0  probe selesai dan sekurangnya satu arsip ditemukan.
1  tidak satu pun arsip ditemukan. Ini menandakan pola URL salah atau jaringan
   diblokir, bukan bahwa datanya tidak ada. Wajib diperiksa manusia.
2  galat tak terduga saat menulis laporan.

Catatan kejujuran: daftar simbol di bawah dipilih tangan sebagai sampel probe.
Ia **bukan** semesta layak dan tidak boleh dipakai sebagai semesta run. Semesta
layak untuk LTF adalah utang terbuka ADR-S001 §5 butir 2.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

BASIS = "https://data.binance.vision/data/futures/um/monthly/klines"

# Sampel probe: 4 kapitalisasi besar, 4 menengah, 4 kecil/lebih baru.
SIMBOL_PROBE: Tuple[str, ...] = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "ADAUSDT",
    "LINKUSDT",
    "AVAXUSDT",
    "DOTUSDT",
    "ANIMEUSDT",
    "AIOTUSDT",
    "AGTUSDT",
    "ANTUSDT",
)

INTERVAL_PROBE: Tuple[str, ...] = ("5m", "15m")

BULAN_AWAL: Tuple[int, int] = (2020, 1)
BULAN_AKHIR: Tuple[int, int] = (2026, 6)

PEKERJA = 16
BATAS_COBA = 3
TENGGANG_DETIK = 20
DIR_LAPORAN = Path("reports")
NAMA_LAPORAN = "probe_ltf"


def daftar_bulan(awal: Tuple[int, int] = BULAN_AWAL,
                 akhir: Tuple[int, int] = BULAN_AKHIR) -> List[str]:
    """Kembalikan daftar "YYYY-MM" inklusif dari awal sampai akhir."""
    tahun, bulan = awal
    tahun_akhir, bulan_akhir = akhir
    keluar: List[str] = []
    while (tahun, bulan) <= (tahun_akhir, bulan_akhir):
        keluar.append(f"{tahun:04d}-{bulan:02d}")
        bulan += 1
        if bulan > 12:
            bulan = 1
            tahun += 1
    return keluar


def url_arsip(simbol: str, interval: str, bulan: str) -> str:
    """Bangun URL arsip bulanan."""
    return f"{BASIS}/{simbol}/{interval}/{simbol}-{interval}-{bulan}.zip"


def periksa_satu(tugas: Tuple[str, str, str]) -> Dict[str, object]:
    """Kirim HEAD untuk satu (simbol, interval, bulan). Tidak pernah melempar."""
    simbol, interval, bulan = tugas
    alamat = url_arsip(simbol, interval, bulan)
    hasil: Dict[str, object] = {
        "simbol": simbol,
        "interval": interval,
        "bulan": bulan,
        "kode": None,
        "byte": None,
        "galat": None,
    }
    for percobaan in range(BATAS_COBA):
        try:
            permintaan = urllib.request.Request(alamat, method="HEAD")
            with urllib.request.urlopen(permintaan, timeout=TENGGANG_DETIK) as tanggapan:
                hasil["kode"] = int(tanggapan.status)
                panjang = tanggapan.headers.get("Content-Length")
                hasil["byte"] = int(panjang) if panjang is not None else None
                return hasil
        except urllib.error.HTTPError as galat:
            hasil["kode"] = int(galat.code)
            if galat.code == 404:
                return hasil
            hasil["galat"] = f"HTTPError {galat.code}"
        except Exception as galat:  # noqa: BLE001 - probe tidak boleh mati
            hasil["galat"] = f"{type(galat).__name__}: {galat}"
        if percobaan == BATAS_COBA - 1:
            return hasil
    return hasil


def jalankan() -> Dict[str, object]:
    """Jalankan seluruh probe dan kembalikan ringkasan terstruktur."""
    bulan = daftar_bulan()
    tugas = [
        (simbol, interval, satu_bulan)
        for simbol in SIMBOL_PROBE
        for interval in INTERVAL_PROBE
        for satu_bulan in bulan
    ]
    with ThreadPoolExecutor(max_workers=PEKERJA) as kolam:
        baris = list(kolam.map(periksa_satu, tugas))

    per_interval: Dict[str, Dict[str, object]] = {}
    for interval in INTERVAL_PROBE:
        subset = [b for b in baris if b["interval"] == interval]
        ada = [b for b in subset if b["kode"] == 200]
        total_byte = sum(int(b["byte"] or 0) for b in ada)
        per_interval[interval] = {
            "diperiksa": len(subset),
            "ada": len(ada),
            "hilang": len([b for b in subset if b["kode"] == 404]),
            "galat": len([b for b in subset if b["galat"] is not None and b["kode"] != 404]),
            "total_byte_sampel": total_byte,
            "rerata_byte_per_bulan": (total_byte / len(ada)) if ada else 0,
        }

    per_simbol: Dict[str, Dict[str, int]] = {}
    for simbol in SIMBOL_PROBE:
        per_simbol[simbol] = {
            interval: len([
                b for b in baris
                if b["simbol"] == simbol and b["interval"] == interval and b["kode"] == 200
            ])
            for interval in INTERVAL_PROBE
        }

    return {
        "bukan_bukti": True,
        "catatan": (
            "Probe ketersediaan arsip. Bukan backtest, bukan pra-saring. "
            "Tidak boleh dipakai menyimpulkan apa pun tentang strategi."
        ),
        "basis": BASIS,
        "simbol_probe": list(SIMBOL_PROBE),
        "interval_probe": list(INTERVAL_PROBE),
        "bulan_awal": f"{BULAN_AWAL[0]:04d}-{BULAN_AWAL[1]:02d}",
        "bulan_akhir": f"{BULAN_AKHIR[0]:04d}-{BULAN_AKHIR[1]:02d}",
        "jumlah_bulan": len(bulan),
        "per_interval": per_interval,
        "per_simbol": per_simbol,
        "baris": baris,
    }


def ke_markdown(ringkasan: Dict[str, object]) -> str:
    """Susun laporan markdown pendek yang dapat dibaca manusia."""
    garis: List[str] = []
    garis.append("# Probe ketersediaan arsip LTF (5m / 15m)")
    garis.append("")
    garis.append("> **Bukan bukti.** Berkas ini hanya menjawab apakah arsipnya ada.")
    garis.append("> Ia tidak menyentuh harga dan tidak menyimpulkan apa pun tentang strategi.")
    garis.append("")
    garis.append(f"- Basis: `{ringkasan['basis']}`")
    garis.append(f"- Rentang bulan: {ringkasan['bulan_awal']} .. {ringkasan['bulan_akhir']} "
                 f"({ringkasan['jumlah_bulan']} bulan)")
    garis.append(f"- Simbol sampel: {len(ringkasan['simbol_probe'])}")
    garis.append("")
    garis.append("## Ringkasan per interval")
    garis.append("")
    garis.append("| Interval | Diperiksa | Ada (200) | Hilang (404) | Galat | Byte sampel | Rerata byte/bulan |")
    garis.append("|---|---|---|---|---|---|---|")
    per_interval = ringkasan["per_interval"]
    assert isinstance(per_interval, dict)
    for interval, isi in per_interval.items():
        garis.append(
            f"| {interval} | {isi['diperiksa']} | {isi['ada']} | {isi['hilang']} | "
            f"{isi['galat']} | {isi['total_byte_sampel']} | "
            f"{isi['rerata_byte_per_bulan']:.0f} |"
        )
    garis.append("")
    garis.append("## Cakupan per simbol (jumlah bulan yang ada)")
    garis.append("")
    kolom = " | ".join(str(i) for i in ringkasan["interval_probe"])
    garis.append(f"| Simbol | {kolom} |")
    garis.append("|---" * (1 + len(ringkasan["interval_probe"])) + "|")
    per_simbol = ringkasan["per_simbol"]
    assert isinstance(per_simbol, dict)
    for simbol, isi in per_simbol.items():
        nilai = " | ".join(str(isi[str(i)]) for i in ringkasan["interval_probe"])
        garis.append(f"| {simbol} | {nilai} |")
    garis.append("")
    garis.append("## Ekstrapolasi kasar biaya ingest")
    garis.append("")
    garis.append("Angka di bawah adalah perkalian linear dari rerata byte per bulan sampel.")
    garis.append("Ia perkiraan, bukan ukuran. Simbol muda punya lebih sedikit bulan.")
    garis.append("")
    for interval, isi in per_interval.items():
        rerata = float(isi["rerata_byte_per_bulan"] or 0)
        for cacah_simbol in (12, 100, 438):
            perkiraan = rerata * float(ringkasan["jumlah_bulan"]) * cacah_simbol
            garis.append(
                f"- {interval}, {cacah_simbol} simbol, {ringkasan['jumlah_bulan']} bulan: "
                f"~{perkiraan / 1e9:.2f} GB terkompresi"
            )
    garis.append("")
    return "\n".join(garis)


def main() -> int:
    ringkasan = jalankan()
    per_interval = ringkasan["per_interval"]
    assert isinstance(per_interval, dict)
    total_ada = sum(int(i["ada"]) for i in per_interval.values())

    try:
        DIR_LAPORAN.mkdir(parents=True, exist_ok=True)
        (DIR_LAPORAN / f"{NAMA_LAPORAN}.json").write_text(
            json.dumps(ringkasan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (DIR_LAPORAN / f"{NAMA_LAPORAN}.md").write_text(
            ke_markdown(ringkasan), encoding="utf-8"
        )
    except Exception as galat:  # noqa: BLE001
        print(f"GAGAL menulis laporan: {type(galat).__name__}: {galat}", file=sys.stderr)
        return 2

    for interval, isi in per_interval.items():
        print(f"{interval}: ada {isi['ada']} / {isi['diperiksa']}, "
              f"hilang {isi['hilang']}, galat {isi['galat']}, "
              f"rerata {float(isi['rerata_byte_per_bulan']):.0f} byte/bulan")

    if total_ada == 0:
        print("TIDAK SATU PUN arsip ditemukan. Pola URL atau jaringan bermasalah.",
              file=sys.stderr)
        return 1

    print(f"Total arsip ditemukan: {total_ada}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
