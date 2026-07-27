# Provenans sumber dan protokol angkatan

Berkas ini menetapkan **byte mana** yang menjadi sumber jalur scalp, dan
bagaimana kesetiaan angkatan dibuktikan. Nilainya bukan hiasan: tanpa ini,
hasil uji berbicara tentang kode yang kutulis, bukan tentang modul yang
dikirim operator.

## 1. Byte sumber (terukur 2026-07-28 UTC)

Diekstrak dari `LUX_Terminal_v9_web_lux_upgrade.zip` (972.948 B).

| berkas | byte | baris | sha256 | blob git |
|---|---|---|---|---|
| `patterns.py` | 31.887 | 727 | `4a6d013b4366…819d40` | `9ff67d554317c5a28d6a1e092b57988f76a97e65` |
| `strategy.py` | 70.020 | 1.598 | `8623eaaf7006…7b0ae4` | `528d5591a072a4b6c225163e5b0019e053b417bd` |
| `risk.py` | 23.901 | 529 | `4babdc9d101a…20752e` | `114444622d516f07d26718caf27cdf5e6a01377c` |
| `config.py` | 46.688 | 798 | `2de68366ceca…3615b2` | `656455179d9529ba7f31b11f0cb50526f2e9b2db` |

Nilai lengkap ada di `sumber.py`; tabel ini dipendekkan agar terbaca.

**Koreksi catatan lama.** Catatan proyek sebelumnya mencatat `patterns.py`
sebagai **32.886 B**. Itu keliru: 32.886 B adalah ukuran `KNOWN_ISSUES.md`.
Dua ukuran tertukar. Angka di tabel ini terukur, bukan diingat.

## 2. Mengapa `blob git`, bukan hanya `sha256`

`blob git` = `sha1(b"blob <panjang>\0" + isi)`. Nilai ini **identik** dengan SHA
blob yang dikembalikan API GitHub. Jadi bila sebuah berkas didorong ke
repositori ini dan SHA blob balasannya cocok dengan tabel di atas, itu **bukti
byte demi byte** bahwa tidak ada satu karakter pun yang berubah dalam
perjalanan.

Ini menutup lubang yang sudah dua kali menyakiti proyek ini: **ukuran cocok
bukan bukti**, dan `raw.githubusercontent` bukan saluran verifikasi yang dapat
dipakai.

## 3. Protokol angkatan

1. `lux_ltf/sinyal/pola_v9.py` wajib merupakan salinan **byte-identik**
   `patterns.py`. Nol perubahan: bukan nama variabel, bukan komentar, bukan
   spasi, bukan terjemahan istilah. Ini aman dilakukan karena satu-satunya
   impor `patterns.py` adalah `typing` (baris 23) — mengangkatnya tidak menarik
   dependensi apa pun.
2. Seluruh penyesuaian tinggal di adaptor terpisah
   (`lux_ltf/sinyal/adaptor.py`, `lux_ltf/posisi/`), yang **memanggil** berkas
   terangkat.
3. `tests/test_sumber_pola.py` menegakkan (1). Bila `pola_v9.py` ada tetapi
   hash-nya tidak cocok, uji **merah** — angkatan yang tidak setia tidak dapat
   mendarat secara diam-diam.
4. Sebelum `pola_v9.py` ada, gerbang itu berdiri tanpa menghalangi: ia menguji
   bentuk provenans dan mencatat utangnya secara eksplisit.

## 4. Yang sengaja **tidak** diangkat

`engine.py` (184.993 B). Ia lapisan eksekusi hidup — memanggil order book,
bursa, Telegram, dan status posisi. Yang kita butuhkan darinya hanya geometri
masuk/SL/TP, dan itu **ditulis ulang** sebagai adaptor dengan uji sendiri
(ADR-S003 §5 untuk rumus SL baris 1647–1670; ADR-S004 §2 untuk cabang
MARKET/LIMIT). Mengangkat `engine.py` akan menarik seluruh dunia bursa ke dalam
harness uji.

`config.py` juga tidak diangkat: nilai `strategy_profiles`-nya adalah
**keluaran optimasi** (“optimal 95-pair sweep”), jadi ia dibekukan sebagai
tetapan yang dinyatakan di ADR, bukan diimpor sebagai kebenaran.

## 5. Utang terbuka

- `pola_v9.py` belum ada. Angkatannya wajib dilakukan di jendela konteks yang
  **terpisah** dari pembacaan sumbernya (mitigasi 3 aturan 35), lalu SHA blob
  balasan GitHub dibandingkan dengan `9ff67d554317c5a28d6a1e092b57988f76a97e65`.
- `AUDIT.md` (12.440 B) dan `KNOWN_ISSUES.md` (32.886 B) belum dibaca. Cacat
  kebenaran sinyal di dalamnya termasuk lingkup; hasil kinerja yang tercatat
  di dalamnya **tidak**.
