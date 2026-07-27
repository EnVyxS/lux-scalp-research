# ADR-S002 — Spesifikasi dataset LTF, aritmetika jendela, dan anggaran komputasi

- Status: **Diterima**
- Tanggal: 2026-07-28 UTC
- Bergantung pada: ADR-S001
- Melunasi: ADR-S001 §5 butir 1 (sebagian), butir 2 (sebagian), butir 3 (penuh)

## 1. Konteks

Modul `LUX_Terminal_v9_web_lux_upgrade` (208 berkas) telah dibaca pada jalur
sinyalnya: `patterns.py` (727 baris), `strategy.py` (1.598 baris) termasuk
`SweepStrategy` utuh (367–1438), `HTFAnalyzer`, `DivergenceAnalyzer`, dan
`config.py` (798 baris). `engine.py` (184.993 B) dan `exchange.py` **belum**
dibaca; konsekuensinya dicatat di §7.

ADR ini memancangkan dataset apa yang dibutuhkan, dalam jumlah bar yang eksplisit,
sebelum satu byte data diunduh dan sebelum satu angka kinerja terlihat.

## 2. Kontrak data lilin — enam medan, tidak lebih

`strategy.py` baris 59 mendefinisikan:

```
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
```

Itu **seluruh** permukaan data yang dikonsumsi jalur sinyal. Bukti pendukung:

- akses medan di `strategy.py`: `.low` 25×, `.high` 25×, `.close` 18×, `.open` 2×;
- akses medan di `patterns.py`: `.close` 21×, `.high` 5×, `.low` 4×, `.open` 3×,
  `.volume` 2× (lewat `avg_volume` / `volume_expansion`);
- pencarian kata `orderbook`, `depth`, `aggTrades`, `openInterest`, `funding`,
  `premiumIndex`, `markPrice`, `liquidation` di seluruh modul menemukan kecocokan
  hanya di lapisan eksekusi live (`exchange.py`, `engine.py`, `risk.py`) —
  **nol** di `strategy.py` dan **nol** di `patterns.py`.

**Keputusan:** dataset uji adalah klines OHLCV. Order book, tick/aggTrades, open
interest, dan funding **tidak** diperlukan untuk menguji sinyal, entry, TP, dan SL.
Ini menggugurkan rencana ingest `aggTrades`/`bookTicker` yang sempat kuajukan.

## 3. Timeframe yang dibutuhkan — empat, dan tepat empat

| TF | Peran | Bar konteks | Sumber di kode |
|---|---|---|---|
| **5m** | umpan bar dasar `SweepStrategy.update` | `warmup_candles` 1000 | `TIMEFRAME` default `"5m"` (config.py:310); 21 literal `"5m"` |
| **15m** | pemicu `choch_15m`; `swing_high_15m`/`swing_low_15m` untuk penempatan SL; divergensi RSI/MACD | `htf_candles_15m` 160 | `DivergenceAnalyzer.analyze(candles_15m)`; `div_tf` `"15m"` (config.py:455) |
| **1h** | `bias_1h` pengubah keyakinan; `adx_1h` filter regime bertingkat | `htf_candles_1h` 120 | `HTFBias.adx_1h` |
| **4h** | `bias_4h` — **filter keras** | `htf_candles_4h` 120 | dokstring `HTFBias` |

**Keputusan ingest:** hanya **5m** dan **15m** diunduh dari
`data.binance.vision/data/futures/um/monthly/klines`. **1h dan 4h diimpor** dari
release `tier-b-v1` milik `lux-research` (id `359778114`), yang sudah memuat 438
simbol. Ini memotong separuh rencana ingest semula, dan importnya wajib disertai
verifikasi checksum agar bar yang dipakai dua repo identik byte demi byte.

## 4. Warmup pengikat adalah 20 hari, dan bukan ditentukan oleh 5m

Bar konteks dikonversi ke kalender:

- `htf_candles_4h` 120 × 4 jam = **20 hari** ← **pengikat**
- `htf_candles_1h` 120 × 1 jam = 5 hari
- `htf_candles_15m` 160 × 15 menit = 40 jam
- `warmup_candles` 1000 × 5 menit = 3,47 hari

Setiap jendela uji karena itu menuntut **20 hari data pra-jendela**, ditentukan
oleh 4h. Ini berlawanan dengan dugaan wajar bahwa timeframe terkecil yang
menentukan warmup.

Catatan memori terpisah: buffer lilin `SweepStrategy` adalah
`deque(maxlen=max(L*2+5, atr_period+5, regime_range_n+5))` = **105 lilin saja**,
tetapi memori strukturalnya jauh lebih panjang — `max_pivot_age` 500,
`max_ob_age` 200, `max_ifvg_age` 100. Warmup 1000 bar 5m karena itu benar dan
bukan pemborosan: ATR dan regime hanya perlu 105 bar, tetapi pivot dan order
block perlu 500.

## 5. Aritmetika jendela walk-forward

`lux-research` memakai kontrak **kalender** yang sama di 1h dan 4h: latih **180
hari**, uji **90 hari**, embargo **7 hari**. (Di 1h: 4320/2160/168 bar. Di 4h:
1080/540/42 bar.) Kontrak kalender itu dipertahankan di sini; yang berubah hanya
cacah barnya.

Bar per hari: 5m = 288 · 15m = 96 · 1h = 24 · 4h = 6.

| TF | pemanasan (20 hari) | latih (180 hari) | embargo (7 hari) | uji (90 hari) | total/jendela |
|---|---|---|---|---|---|
| **5m** | 5.760 | 51.840 | 2.016 | 25.920 | **85.536** |
| **15m** | 1.920 | 17.280 | 672 | 8.640 | **28.512** |
| 1h | 480 | 4.320 | 168 | 2.160 | 7.128 |
| 4h | 120 | 1.080 | 42 | 540 | 1.782 |

**Keputusan:** angka bar di atas mengikat. Memindahkan `panjang_latih = 4320`
mentah dari `lux-research` ke 5m akan berarti latih **15 hari**, bukan 180 —
cacat kelas yang sama dengan `MAKS_RASIO_DATAR` yang dipakai identik di 1h dan 4h
di repo utama.

## 6. Anggaran komputasi — batasan sebenarnya

Jendela 4h yang dipakai H-013/H-014/H-015 memuat 1.862 bar. Maka:

- satu jendela **5m** = 85.536 / 1.862 = **45,9×** beban jendela 4h;
- satu jendela **15m** = 28.512 / 1.862 = **15,3×**.

Waktu nyata H-015 pada 437 simbol: sel K 70 s, F 74 s, A 162 s. Bila biaya
linear terhadap cacah bar — asumsi yang **belum diuji** — maka:

| | 5m | 15m |
|---|---|---|
| sel K | ~53,6 menit | ~17,9 menit |
| sel F | ~56,6 menit | ~18,9 menit |
| sel A | ~2,07 jam | ~41,3 menit |
| **total 3 sel** | **~3,9 jam** | **~1,3 jam** |

Batas runner adalah **6 jam**. Jadi 5m masuk di atas kertas, tetapi dengan
margin yang tipis, dan asumsi linearitas hampir pasti optimistis: deteksi 15 pola
per bar dengan iterasi atas daftar pivot lebih mahal per bar daripada breakout
Donchian yang dipakai H-001.

**Keputusan:** jalur pertama dijalankan pada **15m**, dan penyimpangan dari
desain 5m modul dicatat terang-terangan sebagai penyimpangan — bukan disamarkan
sebagai hasil setara. 5m dijalankan sesudah biaya nyata 15m terukur. Bila 15m
mati oleh biaya transaksi, 5m tidak perlu dibiayai, karena drag fee di 5m lebih
buruk, bukan lebih baik.

## 7. Utang yang tetap terbuka

1. **`engine.py` belum dibaca**, dan itu bukan detail. `Signal` (strategy.py:134)
   **tidak** memuat `entry`, `sl`, atau `tp`. Ketiganya dihitung di luar kelas
   strategi. Menguji entry/TP/SL secara setia berarti membangun ulang lapisan
   manajemen order itu, dan setiap keputusan di sana harus dipatok di ADR sebelum
   angka terlihat — kalau tidak, ia ruang bebas untuk overfit yang tidak
   terhitung di PBO.
2. **`min_rr` punya dua sumber kebenaran.** Tanda tangan `find_tp_levels`
   memancangkan `min_rr: float = 1.5`; `config.py` memancangkan `min_rr` 2.0.
   Mana yang berlaku bergantung pada apa yang diteruskan `engine.py`. Selisihnya
   memindahkan ambang pulang-pokok dari winrate ~38% ke ~43,5% pada biaya 0,306R.
   **Ini memerlukan verifikasi.**
3. **Split TP versus `enable_partial_tp: False`.** `find_tp_levels` menyetel
   `is_split = tp2 > 0.0` setiap kali ada TP2 struktural valid, sementara konfig
   mematikan partial TP. Salah satu tidak berlaku di jalur live.
   **Ini memerlukan verifikasi.**
4. **Model biaya LTF belum dipatok.** Dari `lux-research` H-001:
   `rerata_transaksi_R` 0,03434 pada `rerata_stop_frac` 0,035676, yakni biaya
   ≈0,001225 fraksi harga pulang-pergi. Pada `min_sl_distance_pct` 0,004 milik
   modul, itu menjadi **≈0,306R per perdagangan**, dan ambang pulang-pokok pada
   RR 2,0 menjadi winrate ≈**43,5%** (tanpa biaya cukup 33,3%). Angka 0,001225
   terukur pada holding 1 jam; berlakunya pada holding menit
   **memerlukan verifikasi**.
5. **Semesta layak LTF belum ditetapkan.** `universe_layak_v2` (438 simbol)
   dibangun dari data 1h dan tidak otomatis berlaku pada 5m/15m.

## 8. Prediksi yang dipra-registrasi oleh ADR ini

Dicatat sebelum angka apa pun terlihat, agar dapat meleset secara terbuka.

- **R-Y1** — run 3 sel pada **5m** atas semesta layak penuh dengan kalender
  180/90/7 akan melampaui **4 jam** waktu nyata, yakni asumsi linearitas di §6
  terbukti optimistis.
- **R-Y2** — run 3 sel pada **15m** akan selesai di bawah **2 jam**.
- **R-Y3** — nilai `min_rr` efektif yang diteruskan `engine.py` adalah **2.0**
  (konfig menang atas default 1.5 di tanda tangan fungsi).
- **R-Y4** — `funding maks` per perdagangan pada 15m akan turun di bawah
  **0,05R** (bandingkan H-015 sel K: 0,4243R), sehingga gerbang
  `invarian_risiko` **lulus** untuk pertama kalinya dalam riwayat proyek.

## 9. Larangan yang ditambahkan ADR ini

- Dilarang memindahkan cacah bar `lux-research` mentah ke timeframe lain.
  Kontrak yang dipertahankan adalah kalender, bukan bar.
- Dilarang mengunduh 1h/4h ulang bila `tier-b-v1` dapat diimpor dengan checksum
  cocok.
- Dilarang menjalankan run bergerbang sebelum model biaya §7 butir 4 dipatok.
- Dilarang menyebut hasil 15m sebagai hasil modul 5m. Setiap laporan wajib
  memuat timeframe dasar di medan tersendiri.
