"""Ingest klines bulanan Binance USDT-M untuk timeframe rendah (5m, 15m).

Dipatok oleh ADR-S005:

- §2  hanya **5m** dan **15m** diunduh di sini. 1h, 4h, dan funding shard
      *diimpor* dari release `tier-b-v1` milik `lux-research` (id 359778114)
      dengan checksum wajib cocok — bukan diunduh ulang.
- §2  kontrak lilin enam medan (ADR-S002 §2): ts, open, high, low, close,
      volume. Sembilan kolom sisa arsip Binance dibuang di sini, bukan nanti.
- §6  ingest penuh 438 simbol **dilarang** sampai `reports/probe_ltf.md`
      terbaca. Modul ini memasang pagar keras: lebih dari BATAS_SIMBOL_TANPA_IZIN
      simbol menghentikan proses dengan kode keluar 2.

Runner `lux-research` tidak memuat `requests` (numpy, pandas, pyarrow, pyyaml
saja), jadi urllib dipakai langsung. Tidak ada dependensi baru.

Kode keluar
-----------
0  selesai; manifest tertulis
2  pagar (pagar simbol dilanggar, atau argumen tidak sah)
3  pengaman mati (pyarrow tidak ada, direktori keluaran tidak dapat ditulis)
4  tidak dapat dinilai (nol arsip terunduh padahal ada yang diminta)
"""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# Tetapan
# ----------------------------------------------------------------------------

BASIS = "https://data.binance.vision/data/futures/um/monthly/klines"

INTERVAL = ("5m", "15m")

MENIT_PER_INTERVAL: Dict[str, int] = {"5m": 5, "15m": 15}

MENIT_PER_HARI = 1440

# Dua belas simbol probe. Ini **bukan** semesta layak (ADR-S005 §7): semesta
# layak LTF harus diturunkan dari kriteria ADR-003 atas bar 5m/15m. Daftar ini
# hanya untuk membuktikan bentuk berkas, checksum, dan parser pada biaya kecil.
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

BULAN_AWAL = (2020, 1)
BULAN_AKHIR = (2026, 6)

BATAS_SIMBOL_TANPA_IZIN = 12

PEKERJA = 8
BATAS_COBA = 3
TENGGANG_DETIK = 60
JEDA_COBA_DETIK = 2.0

DIR_ASET = Path("aset")
DIR_LAPORAN = Path("reports")
NAMA_LAPORAN = "ingest_ltf"

KOLOM_ARSIP = 12


# ----------------------------------------------------------------------------
# Aritmetika bulan dan nama berkas
# ----------------------------------------------------------------------------


def bulan_berurut(
    awal: Tuple[int, int], akhir: Tuple[int, int]
) -> List[Tuple[int, int]]:
    """Daftar (tahun, bulan) inklusif dari `awal` sampai `akhir`."""
    if awal > akhir:
        raise ValueError(f"bulan awal {awal} melampaui bulan akhir {akhir}")
    keluaran: List[Tuple[int, int]] = []
    tahun, bulan = awal
    while (tahun, bulan) <= akhir:
        keluaran.append((tahun, bulan))
        if bulan == 12:
            tahun, bulan = tahun + 1, 1
        else:
            bulan += 1
    return keluaran


def nama_arsip(simbol: str, interval: str, tahun: int, bulan: int) -> str:
    return f"{simbol}-{interval}-{tahun:04d}-{bulan:02d}.zip"


def url_arsip(simbol: str, interval: str, tahun: int, bulan: int) -> str:
    return f"{BASIS}/{simbol}/{interval}/{nama_arsip(simbol, interval, tahun, bulan)}"


def url_checksum(simbol: str, interval: str, tahun: int, bulan: int) -> str:
    return url_arsip(simbol, interval, tahun, bulan) + ".CHECKSUM"


def bar_diharapkan(tahun: int, bulan: int, interval: str) -> int:
    """Cacah bar penuh untuk satu bulan kalender pada `interval`.

    Tidak memperhitungkan downtime bursa atau tanggal listing simbol; selisih
    terhadap cacah nyata dilaporkan sebagai `bar_hilang`, bukan disembunyikan.
    """
    if interval not in MENIT_PER_INTERVAL:
        raise ValueError(f"interval tidak dikenal: {interval}")
    hari = calendar.monthrange(tahun, bulan)[1]
    return hari * MENIT_PER_HARI // MENIT_PER_INTERVAL[interval]


# ----------------------------------------------------------------------------
# Unduh dan checksum
# ----------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checksum_dari_teks(teks: str) -> str:
    """Ambil hash dari isi berkas `.CHECKSUM` Binance.

    Bentuknya `"<sha256>  <nama berkas>"`. Hanya token pertama yang dipakai,
    dan dinormalkan ke huruf kecil.
    """
    potong = teks.strip().split()
    if not potong:
        raise ValueError("berkas CHECKSUM kosong")
    hash_ = potong[0].lower()
    if len(hash_) != 64 or any(c not in "0123456789abcdef" for c in hash_):
        raise ValueError(f"hash CHECKSUM tidak sah: {potong[0]!r}")
    return hash_


class TidakAda(Exception):
    """Arsip tidak ada (404). Normal: simbol belum listing pada bulan itu."""


def unduh(
    url: str, tenggang: float = TENGGANG_DETIK, batas_coba: int = BATAS_COBA
) -> bytes:
    galat_akhir: Optional[BaseException] = None
    for coba in range(batas_coba):
        try:
            with urllib.request.urlopen(url, timeout=tenggang) as tanggapan:
                return tanggapan.read()
        except urllib.error.HTTPError as galat:
            if galat.code == 404:
                raise TidakAda(url) from galat
            galat_akhir = galat
        except Exception as galat:  # noqa: BLE001 - jaringan apa pun
            galat_akhir = galat
        if coba + 1 < batas_coba:
            time.sleep(JEDA_COBA_DETIK * (coba + 1))
    raise RuntimeError(f"gagal mengunduh {url}: {galat_akhir!r}")


# ----------------------------------------------------------------------------
# Parsing arsip
# ----------------------------------------------------------------------------


def baris_dari_zip(isi: bytes) -> List[List[str]]:
    """Baca satu-satunya anggota CSV di dalam zip menjadi daftar baris.

    Arsip Binance berubah bentuk di tengah riwayat: berkas lama tanpa baris
    tajuk, berkas baru dengan tajuk `open_time,open,high,...`. Tajuk dikenali
    dari kolom pertama yang bukan angka, lalu dibuang.
    """
    with zipfile.ZipFile(io.BytesIO(isi)) as arsip:
        anggota = [n for n in arsip.namelist() if n.lower().endswith(".csv")]
        if len(anggota) != 1:
            raise ValueError(f"diharapkan 1 anggota csv, ditemukan {len(anggota)}")
        with arsip.open(anggota[0]) as aliran:
            teks = io.TextIOWrapper(aliran, encoding="utf-8", newline="")
            baris = [b for b in csv.reader(teks) if b]
    if baris and not baris[0][0].strip().lstrip("-").isdigit():
        baris = baris[1:]
    return baris


def ke_lilin(baris: Sequence[Sequence[str]]) -> List[Tuple[int, float, float, float, float, float]]:
    """Ubah baris arsip menjadi lilin enam medan.

    Sembilan kolom sisa (close_time, quote_volume, count, taker_buy_*, ignore)
    dibuang di sini. Jalur sinyal tidak pernah membacanya (ADR-S002 §2), jadi
    menyimpannya hanya menaikkan byte tanpa menaikkan daya uji.
    """
    keluaran: List[Tuple[int, float, float, float, float, float]] = []
    for i, b in enumerate(baris):
        if len(b) != KOLOM_ARSIP:
            raise ValueError(
                f"baris {i} punya {len(b)} kolom, diharapkan {KOLOM_ARSIP}"
            )
        ts = int(float(b[0]))
        # Arsip lama memakai milidetik; sebagian berkas baru mikrodetik.
        if ts > 10**14:
            ts //= 1000
        keluaran.append(
            (
                ts,
                float(b[1]),
                float(b[2]),
                float(b[3]),
                float(b[4]),
                float(b[5]),
            )
        )
    return keluaran


def periksa_urutan(
    ts: Sequence[int], interval: str
) -> Tuple[bool, int, int]:
    """Kembalikan (monoton_naik, cacah_bar_hilang, cacah_duplikat).

    `cacah_bar_hilang` menghitung bar yang seharusnya ada di antara dua cap
    waktu berurutan. Ini audit integritas, bukan penambalan: tidak ada bar yang
    diinterpolasi.
    """
    langkah = MENIT_PER_INTERVAL[interval] * 60_000
    monoton = True
    hilang = 0
    duplikat = 0
    for a, b in zip(ts, ts[1:]):
        delta = b - a
        if delta == 0:
            duplikat += 1
            continue
        if delta < 0:
            monoton = False
            continue
        if delta > langkah:
            hilang += delta // langkah - 1
    return monoton, int(hilang), duplikat


# ----------------------------------------------------------------------------
# Keluaran parquet
# ----------------------------------------------------------------------------


def tulis_parquet(
    lilin: Sequence[Tuple[int, float, float, float, float, float]], keluar: Path
) -> int:
    import pyarrow as pa  # impor lambat: modul tetap dapat diuji tanpa pyarrow
    import pyarrow.parquet as pq

    tabel = pa.table(
        {
            "ts": pa.array([l[0] for l in lilin], type=pa.int64()),
            "open": pa.array([l[1] for l in lilin], type=pa.float64()),
            "high": pa.array([l[2] for l in lilin], type=pa.float64()),
            "low": pa.array([l[3] for l in lilin], type=pa.float64()),
            "close": pa.array([l[4] for l in lilin], type=pa.float64()),
            "volume": pa.array([l[5] for l in lilin], type=pa.float64()),
        }
    )
    keluar.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabel, keluar, compression="zstd")
    return keluar.stat().st_size


# ----------------------------------------------------------------------------
# Satu unit kerja
# ----------------------------------------------------------------------------


def kerjakan_satu(
    simbol: str,
    interval: str,
    tahun: int,
    bulan: int,
    dir_aset: Path,
    paksa: bool = False,
) -> Dict[str, object]:
    catatan: Dict[str, object] = {
        "simbol": simbol,
        "interval": interval,
        "bulan": f"{tahun:04d}-{bulan:02d}",
        "status": "galat",
    }
    keluar = dir_aset / f"ohlcv_{interval}" / simbol / f"{tahun:04d}-{bulan:02d}.parquet"
    if keluar.exists() and not paksa:
        catatan["status"] = "sudah_ada"
        catatan["byte_parquet"] = keluar.stat().st_size
        return catatan
    try:
        isi = unduh(url_arsip(simbol, interval, tahun, bulan))
    except TidakAda:
        catatan["status"] = "tidak_ada"
        return catatan
    except Exception as galat:  # noqa: BLE001
        catatan["alasan"] = repr(galat)
        return catatan

    catatan["byte_zip"] = len(isi)
    catatan["sha256_zip"] = sha256_hex(isi)

    # Checksum resmi. Bila berkas CHECKSUM tidak ada, itu dicatat sebagai
    # `checksum: "tidak_ada"` dan **bukan** dianggap lulus.
    try:
        teks = unduh(url_checksum(simbol, interval, tahun, bulan)).decode("utf-8")
        resmi = checksum_dari_teks(teks)
        catatan["checksum"] = "cocok" if resmi == catatan["sha256_zip"] else "beda"
        catatan["sha256_resmi"] = resmi
    except TidakAda:
        catatan["checksum"] = "tidak_ada"
    except Exception as galat:  # noqa: BLE001
        catatan["checksum"] = "galat"
        catatan["alasan_checksum"] = repr(galat)

    if catatan.get("checksum") == "beda":
        catatan["status"] = "checksum_beda"
        return catatan

    try:
        lilin = ke_lilin(baris_dari_zip(isi))
    except Exception as galat:  # noqa: BLE001
        catatan["alasan"] = repr(galat)
        return catatan

    if not lilin:
        catatan["status"] = "kosong"
        return catatan

    monoton, hilang, duplikat = periksa_urutan([l[0] for l in lilin], interval)
    diharapkan = bar_diharapkan(tahun, bulan, interval)
    catatan.update(
        {
            "bar": len(lilin),
            "bar_diharapkan": diharapkan,
            "bar_hilang": hilang,
            "bar_duplikat": duplikat,
            "monoton_naik": monoton,
            "ts_awal": lilin[0][0],
            "ts_akhir": lilin[-1][0],
        }
    )

    try:
        catatan["byte_parquet"] = tulis_parquet(lilin, keluar)
        catatan["sha256_parquet"] = sha256_hex(keluar.read_bytes())
        catatan["berkas"] = str(keluar)
        catatan["status"] = "ok"
    except Exception as galat:  # noqa: BLE001
        catatan["alasan"] = repr(galat)
    return catatan


# ----------------------------------------------------------------------------
# Laporan
# ----------------------------------------------------------------------------


def ringkas(catatan: Sequence[Dict[str, object]]) -> Dict[str, object]:
    hitung: Dict[str, int] = {}
    for c in catatan:
        kunci = str(c.get("status"))
        hitung[kunci] = hitung.get(kunci, 0) + 1
    byte_zip = sum(int(c.get("byte_zip", 0) or 0) for c in catatan)
    byte_pq = sum(int(c.get("byte_parquet", 0) or 0) for c in catatan)
    bar = sum(int(c.get("bar", 0) or 0) for c in catatan)
    hilang = sum(int(c.get("bar_hilang", 0) or 0) for c in catatan)
    duplikat = sum(int(c.get("bar_duplikat", 0) or 0) for c in catatan)
    checksum_beda = sum(1 for c in catatan if c.get("checksum") == "beda")
    checksum_absen = sum(1 for c in catatan if c.get("checksum") == "tidak_ada")
    tak_monoton = sum(1 for c in catatan if c.get("monoton_naik") is False)
    return {
        "cacah_unit": len(catatan),
        "per_status": hitung,
        "total_byte_zip": byte_zip,
        "total_byte_parquet": byte_pq,
        "total_bar": bar,
        "total_bar_hilang": hilang,
        "total_bar_duplikat": duplikat,
        "checksum_beda": checksum_beda,
        "checksum_tidak_ada": checksum_absen,
        "berkas_tak_monoton": tak_monoton,
    }


def tulis_laporan(
    catatan: Sequence[Dict[str, object]],
    ringkasan: Dict[str, object],
    dir_laporan: Path,
    nama: str,
    detik: float,
) -> None:
    dir_laporan.mkdir(parents=True, exist_ok=True)
    isi = {
        "nama": nama,
        "dibuat_utc": datetime.now(timezone.utc).isoformat(),
        "detik": round(detik, 2),
        "catatan_adr": "ADR-S005 §2 (cermin + 5m/15m), §6 (pagar 12 simbol)",
        "bukan_bukti": True,
        "ringkasan": ringkasan,
        "unit": list(catatan),
    }
    (dir_laporan / f"{nama}.json").write_text(
        json.dumps(isi, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    baris = [
        f"# Ingest LTF — {nama}",
        "",
        "Ini **provenans data**, bukan bukti kinerja (`bukan_bukti: true`).",
        "",
        f"- dibuat: {isi['dibuat_utc']}",
        f"- detik: {isi['detik']}",
        "",
        "## Ringkasan",
        "",
        "| medan | nilai |",
        "|---|---|",
    ]
    for kunci, nilai in ringkasan.items():
        baris.append(f"| `{kunci}` | {nilai} |")
    baris += [
        "",
        "## Integritas",
        "",
        f"- checksum beda: **{ringkasan['checksum_beda']}** (wajib 0)",
        f"- checksum tidak ada: {ringkasan['checksum_tidak_ada']}",
        f"- berkas tak monoton: **{ringkasan['berkas_tak_monoton']}** (wajib 0)",
        f"- bar hilang: {ringkasan['total_bar_hilang']} dari {ringkasan['total_bar']}",
        f"- bar duplikat: {ringkasan['total_bar_duplikat']}",
        "",
        "Bar hilang **tidak** ditambal. Interpolasi akan mengarang harga.",
        "",
    ]
    (dir_laporan / f"{nama}.md").write_text("\n".join(baris), encoding="utf-8")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def bangun_argumen(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest klines 5m/15m Binance USDT-M")
    p.add_argument("--interval", nargs="+", default=list(INTERVAL))
    p.add_argument("--simbol", nargs="+", default=list(SIMBOL_PROBE))
    p.add_argument("--bulan-awal", default=f"{BULAN_AWAL[0]}-{BULAN_AWAL[1]:02d}")
    p.add_argument("--bulan-akhir", default=f"{BULAN_AKHIR[0]}-{BULAN_AKHIR[1]:02d}")
    p.add_argument("--pekerja", type=int, default=PEKERJA)
    p.add_argument("--dir-aset", default=str(DIR_ASET))
    p.add_argument("--dir-laporan", default=str(DIR_LAPORAN))
    p.add_argument("--nama", default=NAMA_LAPORAN)
    p.add_argument("--paksa", action="store_true")
    p.add_argument(
        "--izin-penuh",
        default="",
        help=("alasan tertulis untuk melampaui pagar "
              f"{BATAS_SIMBOL_TANPA_IZIN} simbol (ADR-S005 §6)"),
    )
    return p.parse_args(argv)


def urai_bulan(teks: str) -> Tuple[int, int]:
    potong = teks.split("-")
    if len(potong) != 2:
        raise ValueError(f"bulan harus 'YYYY-MM', bukan {teks!r}")
    return int(potong[0]), int(potong[1])


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = bangun_argumen(argv)

    simbol = list(dict.fromkeys(args.simbol))
    if len(simbol) > BATAS_SIMBOL_TANPA_IZIN and not args.izin_penuh.strip():
        print(
            f"PAGAR: {len(simbol)} simbol melampaui batas "
            f"{BATAS_SIMBOL_TANPA_IZIN}. ADR-S005 §6 melarang ingest penuh "
            "sebelum reports/probe_ltf.md terbaca. Pakai --izin-penuh '<alasan>' "
            "bila pagar ini memang sudah dilunasi oleh ADR.",
            file=sys.stderr,
        )
        return 2

    for iv in args.interval:
        if iv not in MENIT_PER_INTERVAL:
            print(f"PAGAR: interval {iv!r} bukan 5m/15m.", file=sys.stderr)
            return 2

    try:
        awal = urai_bulan(args.bulan_awal)
        akhir = urai_bulan(args.bulan_akhir)
        bulan = bulan_berurut(awal, akhir)
    except ValueError as galat:
        print(f"PAGAR: {galat}", file=sys.stderr)
        return 2

    try:
        import pyarrow  # noqa: F401
    except Exception as galat:  # noqa: BLE001
        print(f"PENGAMAN MATI: pyarrow tidak tersedia: {galat!r}", file=sys.stderr)
        return 3

    dir_aset = Path(args.dir_aset)
    try:
        dir_aset.mkdir(parents=True, exist_ok=True)
    except Exception as galat:  # noqa: BLE001
        print(f"PENGAMAN MATI: {dir_aset} tidak dapat ditulis: {galat!r}", file=sys.stderr)
        return 3

    tugas = [
        (s, iv, t, b)
        for iv in args.interval
        for s in simbol
        for (t, b) in bulan
    ]
    print(
        f"ingest: {len(simbol)} simbol × {len(args.interval)} interval × "
        f"{len(bulan)} bulan = {len(tugas)} unit"
    )

    mulai = time.time()
    catatan: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.pekerja)) as kolam:
        masa_depan = {
            kolam.submit(kerjakan_satu, s, iv, t, b, dir_aset, args.paksa): (s, iv, t, b)
            for (s, iv, t, b) in tugas
        }
        for n, selesai in enumerate(as_completed(masa_depan), start=1):
            catatan.append(selesai.result())
            if n % 100 == 0:
                print(f"  {n}/{len(tugas)} unit", flush=True)

    catatan.sort(
        key=lambda c: (str(c["interval"]), str(c["simbol"]), str(c["bulan"]))
    )
    ringkasan = ringkas(catatan)
    detik = time.time() - mulai
    tulis_laporan(catatan, ringkasan, Path(args.dir_laporan), args.nama, detik)

    print(json.dumps(ringkasan, indent=2, ensure_ascii=False))

    if ringkasan["per_status"].get("ok", 0) == 0 and ringkasan["cacah_unit"] > 0:
        sudah = ringkasan["per_status"].get("sudah_ada", 0)
        if sudah == 0:
            print("TIDAK DAPAT DINILAI: nol arsip terunduh.", file=sys.stderr)
            return 4
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
