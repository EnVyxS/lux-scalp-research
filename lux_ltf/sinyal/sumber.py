"""Provenans byte modul sumber `bot_v8`, dan gerbang kesetiaan angkatan.

Diukur pada 2026-07-28 UTC dari `LUX_Terminal_v9_web_lux_upgrade.zip`
(972.948 B) yang dikirim operator, diekstrak ke `bot_v8/`.

Mengapa dua hash, bukan satu:

- `sha256` adalah hash isi biasa;
- `blob` adalah hash objek git, yakni `sha1(b"blob <len>\\0" + isi)`. Ini **sama
  persis** dengan SHA blob yang dikembalikan API GitHub. Jadi bila sebuah berkas
  didorong ke repositori ini dan SHA blob-nya cocok dengan nilai di bawah, itu
  **bukti byte demi byte** bahwa transfernya utuh — bukan sekadar ukuran cocok.

Ukuran saja bukan bukti. Catatan proyek sebelumnya mencatat `patterns.py`
sebagai 32.886 B; itu keliru — 32.886 B adalah ukuran `KNOWN_ISSUES.md`. Nilai
yang benar ada di bawah, terukur, bukan diingat.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Provenans terukur
# ---------------------------------------------------------------------------

SUMBER: Dict[str, Dict[str, object]] = {
    "patterns.py": {
        "byte": 31887,
        "baris": 727,
        "sha256": "4a6d013b436cd9fd4e37e2739602ab714f7f9d17c441d32c5b88dc1548819d40",
        "blob": "9ff67d554317c5a28d6a1e092b57988f76a97e65",
        "catatan": "15 detektor pola; satu-satunya impor adalah typing (baris 23)",
    },
    "strategy.py": {
        "byte": 70020,
        "baris": 1598,
        "sha256": "8623eaaf700618c1633db02add491a7b45d21d03d4e94482fc180b30447b0ae4",
        "blob": "528d5591a072a4b6c225163e5b0019e053b417bd",
        "catatan": "SweepStrategy, HTFAnalyzer, DivergenceAnalyzer, Candle, Signal",
    },
    "risk.py": {
        "byte": 23901,
        "baris": 529,
        "sha256": "4babdc9d101aa4fd8fd447de721a2eccb9a738c7feec329a9301c23ab120752e",
        "blob": "114444622d516f07d26718caf27cdf5e6a01377c",
        "catatan": "sweep_reclaim_ok, btc_correlation_block, clamp_sl_to_valid_side",
    },
    "config.py": {
        "byte": 46688,
        "baris": 798,
        "sha256": "2de68366cecae0ce482ae707fe62b0e1851d11aa926f5a83fab7b9afbf3615b2",
        "blob": "656455179d9529ba7f31b11f0cb50526f2e9b2db",
        "catatan": "strategy_profiles (>=13 kunci, hasil sweep 95 pasang — keluaran optimasi)",
    },
}

# Berkas di repositori ini yang wajib merupakan salinan byte-identik dari sumber.
# Kunci: jalur relatif di repo. Nilai: nama berkas sumber di `SUMBER`.
BERKAS_DIANGKAT: Dict[str, str] = {
    "lux_ltf/sinyal/pola_v9.py": "patterns.py",
}

# `engine.py` (184.993 B) TIDAK diangkat. Ia lapisan eksekusi hidup: memanggil
# order book, bursa, telegram, dan status. Yang diambil darinya adalah geometri
# masuk/SL/TP, dan itu ditulis ulang sebagai adaptor dengan uji sendiri
# (ADR-S003 §5, ADR-S004 §2) — bukan diangkat.
SENGAJA_TIDAK_DIANGKAT = ("engine.py",)


# ---------------------------------------------------------------------------
# Perkakas hash
# ---------------------------------------------------------------------------


def sha256_isi(isi: bytes) -> str:
    return hashlib.sha256(isi).hexdigest()


def blob_git(isi: bytes) -> str:
    """Hitung SHA objek blob git untuk `isi`.

    Sama dengan `git hash-object` dan dengan SHA blob yang dikembalikan API
    GitHub, sehingga dapat dipakai untuk membuktikan transfer byte demi byte.
    """
    kepala = f"blob {len(isi)}\0".encode("utf-8")
    return hashlib.sha1(kepala + isi).hexdigest()


def periksa_berkas(jalur: Path, nama_sumber: str) -> Dict[str, object]:
    """Bandingkan berkas di disk dengan provenans terekam.

    Mengembalikan dict temuan; tidak melempar. `setia` bernilai True hanya bila
    byte, sha256, dan blob git ketiganya cocok.
    """
    harap = SUMBER[nama_sumber]
    if not jalur.exists():
        return {"ada": False, "setia": False, "nama_sumber": nama_sumber}
    isi = jalur.read_bytes()
    sha = sha256_isi(isi)
    blob = blob_git(isi)
    return {
        "ada": True,
        "nama_sumber": nama_sumber,
        "byte": len(isi),
        "byte_harap": harap["byte"],
        "sha256": sha,
        "sha256_harap": harap["sha256"],
        "blob": blob,
        "blob_harap": harap["blob"],
        "setia": (
            len(isi) == harap["byte"]
            and sha == harap["sha256"]
            and blob == harap["blob"]
        ),
    }


def utang_angkatan(akar: Optional[Path] = None) -> Dict[str, Dict[str, object]]:
    """Status setiap berkas yang seharusnya diangkat."""
    dasar = akar or Path(".")
    return {
        jalur: periksa_berkas(dasar / jalur, nama)
        for jalur, nama in BERKAS_DIANGKAT.items()
    }
