# ADR-S005 — Dataset sebagai cermin `lux-research` ditambah 5m/15m, dan cara uji yang identik

- Status: **Diterima**
- Tanggal: 2026-07-28 UTC
- Bergantung pada: ADR-S001, ADR-S002, ADR-S003, ADR-S004
- **Mengoreksi: ADR-S002 §6** (urutan 15m-dahulu diturunkan dari keputusan metodologis menjadi keputusan urutan biaya)
- **Melunasi: ADR-S002 §7 butir 5 (sebagian)**

## 1. Arahan yang mengikat ADR ini

Arahan operator, 2026-07-28 02:04 WIB, dikutip apa adanya:

> DATASET KITA AKAN BUAT MIRIP SEPERTI YANG SUDAH ADA DI lux-research BEDANYA
> HANYA PENAMBAHAN 5 MENIT DAN 15 MENIT TIMEFRAME, CARA UJI KESELURUHANNYA
> TETAP SAMA DENGAN CARA UJI DI lux-research

Dua hal diputuskan oleh arahan itu, dan keduanya menutup pertanyaan yang sempat
kubuka sendiri:

1. Dataset LTF **bukan** tingkat data baru yang minimal. Ia **cermin** dataset
   `lux-research` dengan dua timeframe **ditambahkan**.
2. Prosedur uji **bukan** ruang desain. Ia disalin, bukan ditemukan ulang.

Aku menerima keduanya. Yang tidak boleh kulakukan adalah menerimanya secara
verbal lalu menyimpang secara diam-diam di dalam kode; karena itu §4 mencatat
dua penyimpangan yang tetap dipaksa oleh strategi yang diuji, beserta arah
keketatannya.

## 2. Dataset — cermin `tier-b-v1` ditambah dua timeframe

Dataset `lux-research` yang dipakai H-001…H-015 terdiri atas, di release
`tier-b-v1` (id `359778114`):

| Aset | Peran di `lux-research` |
|---|---|
| `ohlcv_1h` | umpan bar dasar H-001…H-013 |
| `ohlcv_4h` | umpan bar dasar H-013/H-014/H-015 (438 simbol dimuat) |
| `funding_shard` | pecahan tarif funding (447 jadwal) — dipakai gerbang `invarian_risiko` dan `funding_ekor` |
| `akhir_sejati*.json` | tanggal akhir hidup simbol (790 simbol di varian 4h) |
| `manifest_aset*.json` | checksum per berkas |
| `universe_layak_v2.json` | semesta layak 438 simbol (ADR-003) |

**Keputusan:** dataset `lux-scalp-research` adalah **himpunan yang sama** ditambah
**`ohlcv_5m`** dan **`ohlcv_15m`**:

```
ohlcv_5m       ← diunduh dari data.binance.vision (klines bulanan, futures/um)
ohlcv_15m      ← diunduh dari data.binance.vision
ohlcv_1h       ← DIIMPOR dari tier-b-v1, checksum wajib cocok
ohlcv_4h       ← DIIMPOR dari tier-b-v1, checksum wajib cocok
funding_shard  ← DIIMPOR dari tier-b-v1, checksum wajib cocok
akhir_sejati   ← DIIMPOR
manifest_aset  ← DIIMPOR, lalu diperluas dengan entri 5m/15m
```

Tata letak direktori, konvensi nama berkas, format parquet, dan disiplin checksum
per berkas **identik** dengan `lux-research`. Manifest baru adalah manifest lama
yang **ditambahi** baris, bukan manifest yang ditulis ulang.

### 2.1 Ini mengoreksi tafsirku atas ADR-S002 §2

ADR-S002 §2 menyimpulkan funding "tidak diperlukan". Kesimpulan itu benar untuk
**jalur sinyal** dan salah untuk **jalur gerbang**: dua dari sebelas gerbang
(`invarian_risiko`, `funding_ekor`) membaca funding. Karena arahan §1 memerintahkan
cara uji yang sama, sebelas gerbang itu berlaku, jadi `funding_shard` menjadi
**wajib**, bukan opsional. ADR-S004 §1 sudah mengoreksi butir order book; ini
mengoreksi butir funding. Dua koreksi atas satu ADR yang sama dalam satu hari
adalah tanda bahwa ADR-S002 §2 ditulis dari pembacaan yang belum lengkap, dan itu
dicatat, bukan dihaluskan.

Efek sampingnya menguntungkan: **R-Y4** (funding maks per perdagangan di 15m
turun di bawah 0,05R sehingga `invarian_risiko` lulus pertama kali) kini dapat
dinilai. Tanpa funding shard, prediksi itu tidak akan pernah dapat diadili.

## 3. Cara uji — disalin, bukan ditemukan ulang

Yang berlaku sama persis seperti `lux-research`:

| Unsur | Nilai yang dipertahankan |
|---|---|
| bentuk kode | `Opsi` / `Konteks` / `Spek` / `jalankan_spek` |
| jumlah gerbang | **11**, tanpa dilunakkan |
| ulangan permutasi | **≥ 300** |
| sel pembanding | `entri_acak` wajib ada di setiap hipotesis |
| p berpasangan | atas **bulan UTC**, ambang **p ≤ 0,05** |
| minimum perdagangan | **≥ 100 per sel** |
| ekspektasi minimum | **0,05R** |
| ambang `invarian_risiko` | **−1,5R** |
| selisih antar-sel | **0,020R** |
| putusan | `LULUS` / `DITOLAK` / `TIDAK DAPAT DINILAI` |
| kode keluar | 0 = DITOLAK/LULUS · 2 = pagar · 3 = pengaman mati · 4 = TIDAK DAPAT DINILAI |
| laporan | `reports/backtest_<nama>.json` + `.md` |
| validasi tambahan | `pbo()` ambang **0,50** · `dsr()` ambang **0,95** · `t > 3,0` |
| koreksi banyak-uji | Šidák atas `N_percobaan` repo ini |
| kontrak jendela | kalender **latih 180 hari / uji 90 hari / embargo 7 hari** |

Cacah bar per jendela tetap seperti ADR-S002 §5 (5m: 5.760/51.840/2.016/25.920;
15m: 1.920/17.280/672/8.640). Yang dipertahankan adalah **kalender**, bukan cacah
bar mentah — memindahkan `panjang_latih = 4320` mentah ke 5m berarti latih 15
hari, bukan 180.

`N_percobaan` repo ini tetap **terpisah** dari `lux-research` selama kedua repo
belum disatukan (ADR-S001). Nilai sekarang: **0**.

## 4. Dua penyimpangan yang tetap dipaksa — dan keduanya mengetatkan

Arahan "cara uji tetap sama" bertabrakan dengan dua temuan kode. Aku tidak dapat
mematuhi keduanya sekaligus, jadi kunyatakan tabrakannya secara terbuka, dan
kupilih sisi yang **membuat uji lebih sulit dilewati**, bukan lebih mudah.

### 4.1 Permutasi berblok tanggal, bukan per perdagangan

`lux-research` mengacak label per perdagangan karena entrinya mandiri.
Di sini `btc_correlation_block` (`risk.py:489`, dipanggil `engine.py:1626`)
memblokir LONG saat bias BTC BEAR dan SHORT saat BULL — tanpa syarat, di seluruh
simbol. Maka semua entri pada satu tanggal UTC berbagi satu variabel pengondisi.

Mengacak per perdagangan akan memecah ketergantungan itu dan menghasilkan p yang
**terlalu kecil**. Artinya: mematuhi "cara uji sama" secara harfiah di titik ini
akan membuat strategi **lebih mudah lulus**. Blok per tanggal menghasilkan p yang
**lebih besar**. Penyimpangan ini karena itu berarah **mengetatkan**, dan itulah
satu-satunya arah penyimpangan yang boleh diambil tanpa persetujuan baru.

Turunannya: `same_dir_open` membuat urutan pemrosesan simbol memengaruhi hasil,
jadi urutan wajib deterministik dan tercatat di `sidik` run.

### 4.2 Proksi fill eksplisit

`lux-research` tidak pernah butuh model fill: ia berdagang pada `close` bar 1h/4h.
Modul ini menetapkan harga entry dari L1 order book (`engine.py:1866`), yang tidak
ada di arsip klines. Proksi dipatok di ADR-S004 §1: MARKET di `close` bar pemicu
ditambah slippage yang **selalu merugikan**; LIMIT post-only terisi **hanya** bila
bar berikutnya benar-benar menyentuh harga limit, kalau tidak **kedaluwarsa tanpa
perdagangan** setelah `entry_ttl_bars`.

Arahnya juga mengetatkan: slippage selalu merugikan dan order yang tidak tersentuh
tidak menghasilkan perdagangan, sehingga cacah perdagangan **turun** dan biaya
**naik** dibanding asumsi naif fill-di-close. Alternatifnya — mengisi setiap sinyal
di harga yang diinginkan — adalah lookahead.

### 4.3 Yang **tidak** boleh menyimpang

Selain 4.1 dan 4.2, tidak ada. Khususnya dilarang: melunakkan salah satu dari 11
gerbang, menurunkan `ulangan` di bawah 300, menghapus sel `entri_acak`, mengganti
satuan p dari bulan UTC ke perdagangan, mengubah ambang di §3, atau menambah
gerbang baru yang tidak ada di `lux-research`.

## 5. Koreksi atas ADR-S002 §6

ADR-S002 §6 memutuskan "jalur pertama dijalankan pada 15m" dan menyebut
penyimpangan dari desain 5m modul sebagai penyimpangan metodologis yang dicatat.
Di bawah arahan §1, kerangka itu salah: cara uji tidak berubah antar timeframe,
jadi menjalankan 15m lebih dahulu **bukan** penyimpangan metode — ia semata
**urutan pembiayaan**.

**Keputusan pengganti:** kedua timeframe dijalankan dengan prosedur yang identik.
15m dijalankan lebih dahulu hanya karena ia ~3× lebih murah (15,3× beban jendela
4h lawan 45,9×), sehingga cacat harness terdeteksi dengan biaya lebih rendah.
Hasil 15m **tidak** menggantikan hasil 5m dan **tidak** boleh dilaporkan sebagai
hasil modul 5m. Setiap laporan wajib memuat `interval` sebagai medan tersendiri,
dan setiap sel dalam satu hipotesis wajib memakai `interval` yang sama.

Bila 15m mati oleh biaya transaksi, 5m tetap dijalankan sekali sebagai
pemeriksaan arah — bukan dibatalkan seperti kata ADR-S002 §6 — karena frekuensi
sinyal yang lebih tinggi dapat mengubah tanda ekspektasi meski drag fee lebih
buruk. Ini pembalikan keputusan lamaku, dan alasannya adalah bahwa "drag fee 5m
lebih buruk" hanya mengikat bila ekspektasi per perdagangan setara, yang belum
terukur.

## 6. Konsekuensi biaya ingest yang belum terukur

Cacah arsip 5m/15m per simbol per bulan sama dengan cacah arsip 1h/4h (satu zip
per simbol per bulan per interval), tetapi **ukurannya** jauh lebih besar: 12×
cacah baris 1h untuk 5m, 4× untuk 15m. Pada 438 simbol × 78 bulan × 2 interval,
ini adalah unduhan terbesar dalam riwayat proyek.

Angka pastinya menunggu `reports/probe_ltf.md`, yang **belum ada di `main`** —
workflow `probe_ltf.yml` belum selesai, gagal, atau tidak pernah terpicu. Tidak
ada alat GitHub Actions yang tersedia untukku, jadi status itu hanya dapat dibaca
operator. **Ini memerlukan verifikasi.**

**Larangan sampai probe terbaca:** dilarang memulai ingest penuh 438 simbol.
Ingest pertama dibatasi pada 12 simbol probe agar bentuk berkas, checksum, dan
parser terbukti pada biaya kecil.

## 7. Semesta layak LTF

`universe_layak_v2.json` (438 simbol) dibangun dari data 1h. Arahan §1 menuntut
cara uji sama, dan cara uji `lux-research` memakai semesta yang **diturunkan dari
kriteria kelayakan ADR-003**, bukan daftar tangan.

**Keputusan:** kriteria ADR-003 diterapkan ulang pada bar 5m dan 15m untuk
menghasilkan `universe_layak_ltf_5m.json` dan `universe_layak_ltf_15m.json`.
Selisih keanggotaan terhadap `universe_layak_v2` wajib dilaporkan sebagai temuan,
karena kriteria bar datar dan likuiditas berperilaku berbeda pada bar menit.
Daftar 12 simbol probe **bukan** semesta dan tidak boleh dipakai untuk run
bergerbang.

Catatan cacat yang diwarisi: `MAKS_RASIO_DATAR = 0.10` di `lux-research` dipakai
identik untuk 1h dan 4h. Menyalinnya identik lagi ke 5m/15m akan memperbesar
cacat yang sama, karena rasio bar datar naik tajam saat interval mengecil. Ambang
ini wajib dinyatakan **per interval** di repo ini, dan nilainya dipatok sebelum
run pertama.

## 8. Utang yang tersisa sesudah ADR ini

1. `reports/probe_ltf.md` belum terbaca (§6).
2. Ambang bar datar per interval belum bernilai (§7).
3. `lux_ltf/ingest.py` dan workflow-nya belum ada.
4. `pola_v9.py` / `sweep_v9.py` / lapisan `posisi/` / `backtest/runner.py` belum ada.
5. `tests.yml` repo ini belum ada; konvensi `lux-research` (`--collect-only`,
   `-rf`, blok FAILED tak terpotong, ekor 200 baris, `set +e`/`kode=$?`, komit
   sebelum penegakan, `[skip ci]`) wajib dicerminkan beserta uji pagarnya.
6. Matriks periode × konfigurasi belum dirancang. Tanpanya `pbo()` tidak dapat
   dijalankan — cacat yang membuat 21 laporan `lux-research` tidak dapat diberi
   PBO surut.

## 9. Prediksi yang dipra-registrasi oleh ADR ini

- **R-Y10** — menerapkan kriteria kelayakan ADR-003 pada bar 15m akan
  **mengecilkan** semesta di bawah 438 simbol, terutama lewat gerbang bar datar,
  bukan lewat gerbang umur data.
- **R-Y11** — permutasi berblok tanggal (§4.1) akan menghasilkan p sekurangnya
  **dua kali** lebih besar daripada permutasi per perdagangan pada data yang sama.
- **R-Y12** — total byte `ohlcv_5m` untuk 12 simbol probe × 78 bulan akan
  melampaui total byte seluruh `ohlcv_4h` di `tier-b-v1` (157.628.619 B untuk 438
  simbol).

## 10. Papan skor arahan ini

| Klaim | Sumber | Status |
|---|---|---|
| dataset = cermin + 5m/15m | arahan operator | **dipatok** |
| cara uji identik | arahan operator | **dipatok**, dua pengecualian di §4 |
| funding wajib | 11 gerbang | **terverifikasi** (gerbang membaca funding) |
| 15m dahulu = metodologi | ADR-S002 §6 | **dicabut** — hanya urutan biaya |
| 5m dibatalkan bila 15m mati | ADR-S002 §6 | **dicabut** |
