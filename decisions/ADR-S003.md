# ADR-S003 — Lapisan manajemen posisi: entry, SL, TP, trailing

- Status: **Diterima**
- Tanggal: 2026-07-28 UTC
- Bergantung pada: ADR-S001, ADR-S002
- Melunasi: ADR-S002 §7 butir 2 (penuh), butir 3 (penuh); butir 1 (sebagian)

## 1. Konteks

`Signal` (strategy.py:134) tidak memuat `entry`, `sl`, maupun `tp`. Ketiganya
dihitung di `engine.py` (184.993 B), kode live-trading yang tidak dapat dipakai
langsung sebagai harness. Menguji entry/TP/SL secara setia karena itu menuntut
lapisan manajemen posisi dibangun ulang. ADR ini memancangkan aturannya dari byte
`engine.py`, dengan nomor baris, sebelum satu angka kinerja terlihat.

## 2. `min_rr` — terselesaikan, dan lebih rumit dari dugaan

`engine.py` meneruskan `min_rr=settings.min_rr` di tiga situs panggilan
(baris 1406, 1679, 3552). Jadi **konfig menang** atas default `1.5` di tanda
tangan `find_tp_levels`, dan nilai efektifnya adalah **2.0**.

**Prediksi R-Y3 (ADR-S002 §8) TEPAT.**

Tetapi baris 1923–1924 memperlihatkan lapisan yang tidak pernah kulihat sebelumnya:

```
_min_rr_eff  = _sprof.get("min_rr", settings.min_rr)
_fallback_rr = _sprof.get("fallback_rr", settings.tp_fallback_rr)
_sl_atr_mult = _sprof.get("sl_atr_multiplier", settings.sl_atr_multiplier)
```

Ada **profil per-strategi** (`_sprof`) yang dapat menimpa `min_rr`,
`fallback_rr`, dan `sl_atr_multiplier` **per sumber setup** (SMC_3L, SMC_2L,
TRENDLINE_BREAK, DOUBLE_TOP, …). Isi `_sprof` **belum dibaca**.

**Konsekuensi metodologis yang wajib diterima:** ini mengalikan ruang parameter
dengan jumlah sumber setup. Setiap medan `_sprof` adalah derajat kebebasan
seleksi, dan karena itu **wajib** ikut terhitung dalam matriks periode ×
konfigurasi yang dimakan `pbo()`. Membiarkannya di luar hitungan akan membuat PBO
melaporkan angka yang terlalu bagus.

**Keputusan:** untuk H-S001, seluruh medan `_sprof` **dibekukan pada nilai
`settings`** — satu nilai untuk semua sumber setup. Profil per-setup hanya boleh
dibuka di hipotesis terpisah, dengan `N_percobaan` bertambah.

## 3. Split TP — tidak ada kontradiksi

Baris 2006:

```
is_split = tp_info['is_split'] and settings.enable_partial_tp
```

`engine.py` meng-**AND** keduanya. Dengan `enable_partial_tp` **False** (default
konfig), split **selalu mati**, walaupun `find_tp_levels` menemukan TP2
struktural yang valid. Dugaanku bahwa ada kontradiksi internal **salah**; yang ada
adalah gerbang berlapis.

Baris 2370: `trail_active = not is_split`. Jadi pada konfig default: **TP1 penuh,
tanpa runner, dan trailing aktif sejak posisi dibuka**.

**Keputusan:** perilaku baku H-S001 adalah TP tunggal di TP1 + trailing aktif
sejak awal. Varian split adalah sel terpisah, bukan parameter bebas.

## 4. Temuan yang tidak kucari, dan yang paling penting di ADR ini

Baris 1997–2000:

```
if rr1 < _min_rr_eff:
    ... "(min {_min_rr_eff}R untuk {_setup_src}). Tidak ada level yang cukup jauh."
```

**Sinyal ditolak** bila kandidat TP struktural terdekat tidak mencapai `min_rr`.
Artinya geometri TP bukan hanya penentu target keluar — ia **saringan entri**.

Konsekuensi yang harus dipahami sebelum menafsirkan angka apa pun:

- melonggarkan `min_rr` **menaikkan** cacah perdagangan, bukan hanya mengubah RR;
- karena itu `min_rr` **tidak boleh** disetel berbeda antar sel TB/TBK/A, kalau
  tidak sel-selnya berbeda pada dua sumbu sekaligus dan selisihnya tidak dapat
  ditafsirkan;
- sel entri acak **A** harus memakai `min_rr` identik, dan saringan `rr1` yang
  sama, kalau tidak perbandingannya tidak sebanding.

Ini pola cacat yang sama dengan H-014 versus H-015 di `lux-research`, di mana
carry safety OFF di satu dan ON di yang lain membuat kaki funding tidak
sebanding walaupun `maks_umur_bar` sudah disetarakan.

## 5. Formula SL — dipatok dari baris 1647–1670

```
atr_buf = atr * _sl_atr_mult

LONG:
  jika swing_ref_sl ada DAN swing_ref_sl < signal.wick_extreme (+ syarat lain):
      sl_anchor = swing_ref_sl
      ps_sl     = sl_anchor - max(atr_buf, entry_ideal * sl_buffer_pct) * 0.5
  selain itu:
      sl_anchor = min(signal.wick_extreme, signal.ob_bottom)
      ps_sl     = sl_anchor - max(atr_buf, entry_ideal * sl_buffer_pct)

SHORT: simetris, dengan max() dan ob_top.

ps_sl = clamp_sl_to_valid_side(side, entry_ideal, ps_sl, min_sl_distance_pct)
```

Tiga hal yang perlu dicatat:

1. Buffer **dibelah setengah** (`* 0.5`) bila jangkar SL memakai swing HTF 15m
   alih-alih wick. Ini pengali tersembunyi kedua, dan ia mengubah `stop_frac`,
   yang langsung mengubah biaya dalam satuan R (lihat §6).
2. Buffer adalah `max(atr_buf, entry * sl_buffer_pct)` — lantai absolut ATR
   **atau** lantai persentase, mana pun yang lebih besar.
3. `clamp_sl_to_valid_side` memaksakan `min_sl_distance_pct` **0,004** sebagai
   lantai terakhir. Lantai inilah yang menentukan biaya dalam R.

## 6. Model biaya — mengapa §5 butir 3 adalah nyawa hipotesis ini

Dari `lux-research` H-001 (terverifikasi byte, `backtest_h001.json`):
`rerata_transaksi_R` 0,03434 pada `rerata_stop_frac` 0,035676, yakni biaya
pulang-pergi ≈ 0,001225 fraksi harga.

Pada `stop_frac` = 0,004 (lantai modul):

```
0,001225 / 0,004 ≈ 0,306 R per perdagangan
```

Ambang pulang-pokok pada RR 2,0: `2p − (1−p) − 0,306 = 0` → **p ≈ 43,5%**
(tanpa biaya cukup 33,3%). Untuk mencapai ekspektasi 0,05R: **p ≈ 45,2%**.

**Keputusan:** `stop_frac` per perdagangan **wajib** dicatat di keluaran
diagnostik, dan `rerata_transaksi_R` wajib dilaporkan bersama `rerata_stop_frac`.
Tanpa keduanya berpasangan, angka biaya tidak dapat ditafsirkan.

## 7. Utang yang tetap terbuka

1. **Aturan harga entry belum dibaca.** `allow_market` pada `Signal` menandakan
   dua jalur (limit di zona OB versus market saat breakout terkonfirmasi volume),
   dan `execution_slicing.py` (5.414 B) menyiratkan pemecahan order. Jalur mana
   yang dipakai menentukan model slippage. **Ini memerlukan verifikasi.**
2. **Isi `_sprof` belum dibaca.** Dibekukan di §2 untuk H-S001, tetapi cacah medan
   dan nilainya harus diketahui sebelum hipotesis profil per-setup dibuka.
3. **`trailing_steps` belum dibaca.** Formatnya `profit_rr:new_sl_rr` dengan
   `min_profit_r_before_trail` 1,2, `trail_swing_len` 8,
   `trail_be_buffer_atr` 0,15. Karena trailing aktif sejak awal pada konfig
   default (§3), aturan ini menentukan sebagian besar distribusi keluar.
   **Ini memerlukan verifikasi.**
4. **`sweep_reclaim_ok`, `btc_correlation_block`** (baris 33) adalah saringan
   entri tambahan yang belum diperiksa. Bila `btc_correlation_block` aktif, ia
   memperkenalkan ketergantungan lintas-simbol yang dapat merusak asumsi
   kemandirian dalam uji permutasi.

## 8. Prediksi baru yang dipra-registrasi

- **R-Y5** — saringan `rr1 < min_rr` (§4) akan menolak lebih dari **50%**
  sinyal yang lolos `SweepStrategy.update`, sehingga cacah perdagangan aktual
  jauh di bawah cacah sinyal mentah.
- **R-Y6** — `_sprof` memuat sekurangnya **empat** sumber setup dengan nilai
  `min_rr` berbeda, artinya ruang parameter efektif modul lebih besar daripada
  ≈21 parameter `patterns.py` yang sudah kucatat.
- **R-Y7** — `btc_correlation_block` ada dan aktif secara baku, sehingga uji
  permutasi harus memakai blok per-tanggal, bukan per-perdagangan bebas.

## 9. Papan skor prediksi jalur ini

| Prediksi | Status |
|---|---|
| R-Y1 (5m > 4 jam) | terbuka |
| R-Y2 (15m < 2 jam) | terbuka |
| **R-Y3 (`min_rr` efektif 2.0)** | **TEPAT** |
| R-Y4 (`invarian_risiko` lulus) | terbuka |
| R-Y5, R-Y6, R-Y7 | terbuka |
