# ADR-S004 — Koreksi model data, ruang parameter sebenarnya, dan struktur uji permutasi

- Status: **Diterima**
- Tanggal: 2026-07-28 UTC
- Bergantung pada: ADR-S001, ADR-S002, ADR-S003
- **Mengoreksi: ADR-S002 §2**
- Melunasi: ADR-S003 §7 butir 1, 2, 3, 4 (semuanya)

## 1. Koreksi yang wajib: order book dibutuhkan, tetapi bukan oleh sinyal

ADR-S002 §2 menyimpulkan "dataset uji adalah klines OHLCV" dan bahwa order book
**tidak** diperlukan. Kesimpulan itu **benar untuk jalur sinyal** dan **salah
untuk model fill**. `engine.py` baris 1866:

```
ob = await self.ex.fetch_orderbook(symbol, depth=5)
best_bid = float(ob["bids"][0][0]) if ob.get("bids") else 0.0
best_ask = float(ob["asks"][0][0]) if ob.get("asks") else float("inf")
```

Harga entry sebenarnya ditetapkan dari L1, lewat dua jalur berbeda (§2). L1
tidak ada di arsip klines bulanan, dan merekonstruksinya dari `bookTicker`
berarti ingest ordo besaran lebih besar daripada klines.

**Keputusan:** backtest memakai **proksi fill eksplisit**, dan proksinya dipatok
di sini alih-alih dipilih diam-diam di dalam kode:

- **Jalur MARKET** (breakout terkonfirmasi): fill di `close` bar pemicu ditambah
  slippage searah sebesar `slippage_bps`, arah selalu merugikan.
- **Jalur LIMIT post-only** (tepi OB): fill **hanya** bila bar berikutnya
  benar-benar menyentuh harga limit (`low <= limit` untuk LONG,
  `high >= limit` untuk SHORT). Bila tidak tersentuh dalam
  `entry_ttl_bars`, order **kedaluwarsa tanpa perdagangan**. Tanpa aturan
  kedaluwarsa ini, backtest akan mengisi order yang di pasar nyata tidak pernah
  terisi — bentuk lookahead yang paling sering meloloskan diri.
- Fill limit **tidak** diberi slippage negatif (post-only maker), tetapi **wajib**
  dibebani rebate/fee maker yang benar, bukan fee taker.

Konsekuensi jujur: cacah perdagangan hasil backtest akan **berbeda** dari cacah
sinyal, dan berbeda pula dari perilaku live. Selisih itu adalah ketidakpastian
yang dilaporkan, bukan ketidakpastian yang disembunyikan.

## 2. Dua jalur entry — dipatok dari baris 1876–1900

```
use_market = False
if signal.allow_market and settings.allow_breakout_market:   # default True
    if patterns.confirm_breakout(candles, sweep_price, side, atr,
                                 buf_atr=breakout_buf_atr,
                                 vol_k=breakout_vol_mult,
                                 vol_lookback=breakout_vol_lookback,
                                 momentum_body_atr=breakout_momentum_body_atr):
        use_market = True
```

- **MARKET** bila breakout terkonfirmasi oleh close tegas + ekspansi volume,
  atau displacement kuat + volume. `allow_breakout_market` default **True**
  (config.py:693).
- **LIMIT post-only (GTX)** di tepi OB pada semua kasus lain, dengan
  `entry_ideal = ob_bottom` (LONG) atau `ob_top` (SHORT) — baris 1641.

Ini penting untuk tafsir: **trendline break memakai MARKET**, jadi ia menanggung
slippage taker; **SMC dan pola reversal memakai LIMIT maker**. Membandingkan sel
TB dengan sel SMC berarti membandingkan dua model biaya sekaligus. Sel entri acak
**A** wajib memakai campuran jalur yang sama, kalau tidak ia bukan pembanding.

## 3. R-Y6 — **TEPAT**. Ruang parameter jauh lebih besar dari catatanku

`config.py:540` mendefinisikan `strategy_profiles` dengan **sekurangnya 13 kunci
sumber setup**: `TRENDLINE_BREAK`, `TRENDLINE_BOUNCE`, `SMC_3L`, `TRIPLE_TOP`,
`TRIPLE_BOTTOM`, `DOUBLE_TOP`, `DOUBLE_BOTTOM`, `HEAD_SHOULDERS`,
`INV_HEAD_SHOULDERS`, `TRIANGLE`, `WEDGE`, `RECTANGLE`, `FLAG`.

Setiap profil menimpa hingga enam medan: `sl_atr_multiplier`, `min_rr`,
`fallback_rr`, `tp1_close_fraction`, `be_after_tp1`, `trailing_steps`.

Nilai `min_rr` yang benar-benar berbeda: **2.5** (TRENDLINE_BREAK), **2.0**
(TRENDLINE_BOUNCE, SMC_3L, DOUBLE_*), **1.5** (TRIPLE_*). `sl_atr_multiplier`
bervariasi 0,30–0,50.

Catatan yang tidak menyenangkan: nilai-nilai ini ditandai `[v8-tuned] optimal
95-pair sweep` di komentar kode. Artinya **profil ini adalah hasil optimasi pada
data**, bukan pilihan apriori. Memakainya apa adanya berarti mewarisi seleksi yang
tidak terhitung. Karena itu §2 ADR-S003 (`_sprof` dibekukan pada nilai
`settings`) **naik dari pilihan praktis menjadi keharusan metodologis**: H-S001
tidak boleh memakai profil ter-tuned, kalau tidak angkanya sudah tercemar sebelum
run pertama.

## 4. Temuan tambahan: 13 medan `tp1_close_fraction` mati secara baku

`engine.py:2006` melakukan `is_split = tp_info['is_split'] and
settings.enable_partial_tp`. Dengan `enable_partial_tp` **False**, `is_split`
selalu False, dan seluruh `tp1_close_fraction` di 13 profil (0,40–0,60) **tidak
pernah dipakai**. Demikian pula `be_after_tp1`, karena TP1 tidak pernah menjadi
penutupan sebagian.

Ini kelas cacat konfigurasi yang sama dengan `universe.maks_rasio_bar_datar` di
`lux-research`: medan ada, ter-tuned, terdokumentasi, dan **tidak pernah dibaca**.

## 5. R-Y7 — **TEPAT**. Uji permutasi harus berblok tanggal

`risk.py:489`:

```
def btc_correlation_block(side, btc_bias, same_dir_open, neutral_max_same_dir):
    if side == "LONG"  and btc_bias == "BEAR": return "melawan regime BTC (BEAR)"
    if side == "SHORT" and btc_bias == "BULL": return "melawan regime BTC (BULL)"
    if btc_bias == "NEUTRAL" and neutral_max_same_dir >= 0 \
       and same_dir_open >= neutral_max_same_dir: return "...cap..."
    return None
```

Dipanggil di `engine.py:1626`. Blok arah bersifat tanpa syarat: seluruh alt
diblokir melawan bias BTC.

**Konsekuensi statistik:** entri di semua simbol pada tanggal yang sama
berbagi satu variabel pengondisi. Perdagangan **tidak** bebas antar simbol.

**Keputusan:** uji permutasi memakai **blok per-tanggal UTC** — label diacak per
tanggal, bukan per perdagangan. Mengacak per perdagangan akan memecah
ketergantungan lintas-simbol dan menghasilkan p yang **terlalu kecil**, yakni
lebih mudah lulus. Asumsi kemandirian yang dipakai `lux-research` **tidak**
berlaku langsung di sini.

Juga: `same_dir_open` menghitung posisi terbuka searah, sehingga urutan
pemrosesan simbol mengubah hasil. Backtest wajib memproses simbol dalam urutan
deterministik dan mencatat urutannya di `sidik` run.

## 6. `sweep_reclaim_ok` — saringan entri ketiga

`risk.py:472`: sinyal hanya lolos bila lilin pemicu **merebut kembali** level
yang di-sweep (close di sisi benar) **dan** body ≥ `min_body_atr × ATR`.
Bila `atr <= 0` cek body dilewati.

Bersama saringan `rr1 < min_rr` (ADR-S003 §4) dan `btc_correlation_block`, ada
**tiga** saringan di antara `SweepStrategy.update` dan perdagangan nyata. Setiap
laporan wajib memuat cacah pada keempat tahap: sinyal mentah → lolos reclaim →
lolos rr1 → lolos blok BTC → terisi. Tanpa corong itu, penurunan cacah
perdagangan tidak dapat diatributkan.

## 7. `trailing_steps` — default global

`config.py:277` menetapkan default global lewat `_steps(...)`;
`min_profit_r_before_trail` **1.2** (config.py:307), dan validator menolak nilai
< 0,5 (config.py:793). Format `(profit_trigger_R, sl_target_R)`. Karena trailing
aktif sejak posisi dibuka pada konfig default (ADR-S003 §3), tangga inilah yang
membentuk sebagian besar distribusi keluar. Contoh profil TRENDLINE_BREAK:
`[(2.5, 0.5), (4.5, 2.5)]` — SL tidak disentuh sampai +2,5R, lalu dipindah ke
+0,5R.

**Keputusan:** H-S001 memakai `trailing_steps` global, bukan per-profil, sejalan
dengan §3.

## 8. Papan skor prediksi jalur ini

| Prediksi | Status |
|---|---|
| R-Y1 (5m > 4 jam) | terbuka |
| R-Y2 (15m < 2 jam) | terbuka |
| R-Y3 (`min_rr` efektif 2.0) | **TEPAT** |
| R-Y4 (`invarian_risiko` lulus) | terbuka |
| R-Y5 (saringan `rr1` menolak >50%) | terbuka |
| **R-Y6 (≥4 sumber setup, `min_rr` berbeda)** | **TEPAT** (≥13 kunci, 3 nilai berbeda) |
| **R-Y7 (`btc_correlation_block` aktif baku)** | **TEPAT** |

## 9. Prediksi baru

- **R-Y8** — aturan kedaluwarsa limit (§1) akan menggugurkan lebih dari **20%**
  sinyal SMC/pola, karena harga sering tidak kembali menyentuh tepi OB.
- **R-Y9** — memakai `strategy_profiles` ter-tuned alih-alih nilai `settings`
  beku akan menaikkan ekspektasi dalam-sampel sekurangnya **20%** sekaligus
  **gagal** pada uji permutasi berblok tanggal — pola yang sama dengan sel F
  H-015, yang menang +20% ekspektasi lalu berakhir TIDAK DAPAT DINILAI.
