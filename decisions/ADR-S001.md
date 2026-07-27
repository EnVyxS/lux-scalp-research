# ADR-S001 — Pemisahan jalur riset scalp/LTF dari lux-research

- Status: **Diterima**
- Tanggal: 2026-07-28 UTC
- Berlaku atas: seluruh isi repositori `EnVyxS/lux-scalp-research`

## 1. Konteks

`lux-research` telah menyelesaikan 21 percobaan bergerbang atas 15 hipotesis: 14 DITOLAK, 1
TIDAK DAPAT DINILAI, nol kandidat. Seluruh hipotesis itu berjalan pada OHLCV 1h atau 4h dengan
funding shard, dan uji kesamaan ADR-040 §3 mengklasifikasikan **semuanya** sebagai satu keluarga
(F1: melanjutkan arah, medan sinyal sejenis, tanda ketergantungan serial sama).

Pemilik proyek memasok satu modul strategi baru yang beroperasi pada timeframe dasar 5m dan
meminta ia diuji dengan harness validasi `lux-research`, tetapi **di repositori terpisah**, agar
riset yang sedang berjalan tidak tercemar.

## 2. Keputusan

1. Jalur scalp/LTF hidup di `EnVyxS/lux-scalp-research` dengan ledger percobaan terpisah.
   `N_percobaan` repo ini dimulai dari **0** dan monoton naik.
2. Penomoran hipotesis di repo ini memakai awalan `H-S` (`H-S001`, `H-S002`, …). Ia **tidak**
   melanjutkan penomoran `H-0XX` milik `lux-research`.
3. Koreksi banyak-pembandingan di repo ini dihitung terhadap `N_percobaan` repo ini saja.
   Šidák: `p ≤ 1 − (1 − 0,05)^(1/N_percobaan)`.
4. Ambang kandidat diwarisi tanpa pelunakan dari ADR-040 `lux-research` sebagaimana diamandemen:
   seluruh gerbang lulus · p ≤ Šidák · t > 3,0 · PBO < 0,50 · DSR > 0,95.
5. Setiap hipotesis **wajib** memuat sel **entri acak** dengan geometri keluar identik. Tanpa sel
   itu, hipotesis tidak dapat dinilai.
6. Setiap hipotesis dipra-registrasi dalam `decisions/` **sebelum** angka pertama terlihat.
   Berkas pra-registrasi memuat ruang parameter, kriteria, dan ambang; sesudah run dimulai ia
   tidak boleh diubah.
7. Migrasi ke `lux-research` hanya lewat tujuh syarat di `README.md` §"Jalan masuk kembali".
   Migrasi menaikkan `N_percobaan` `lux-research` dan wajib dicatat di
   `STATE_LAMPIRAN_ANGKA.md` §0 repo itu.

## 3. Larangan

Dilarang, termasuk atas nama kecepatan:

- memakai `backtest.py` dari modul `LUX_Terminal_v9` (dinyatakan tidak lengkap oleh pemiliknya);
- mengutip hasil yang sudah tercatat di dalam modul itu sebagai bukti apa pun;
- menurunkan `ulangan` permutasi di bawah 300 pada run bergerbang;
- menjalankan run bergerbang tanpa sel entri acak;
- menyimpulkan apa pun dari keluaran pra-saring atau probe, yang selalu ditandai
  `"bukan_bukti": true` dan hanya boleh berkata **tidak**;
- mengubah ambang sesudah melihat angka.

## 4. Konsekuensi yang diterima

Pemisahan ini berarti dua ledger harus dipelihara, dan sebuah temuan yang bagus di repo ini akan
menanggung koreksi **dua kali**: sekali terhadap `N_percobaan` repo ini saat ditemukan, sekali
lagi terhadap `N_percobaan` `lux-research` saat dimigrasikan. Itu memang lebih ketat daripada
menguji langsung di repo utama. Konsekuensi itu diterima secara sadar; ia harga dari menjaga
papan skor lama tetap dapat dibaca.

## 5. Utang yang dibuka oleh ADR ini

1. Verifikasi ketersediaan arsip klines 5m dan 15m Binance Futures UM. **Belum lunas.**
2. Tetapkan semesta layak untuk LTF. Semesta `universe_layak_v2` milik `lux-research` dibangun
   dari data 1h dan **tidak** otomatis berlaku pada 5m.
3. Skala ulang parameter jendela walk-forward. Pada 1h, `panjang_latih` 4.320 bar = 180 hari;
   pada 5m, 4.320 bar = 15 hari. Angka bar tidak boleh dipindahkan mentah.
4. Model biaya. Pada jarak SL 0,4% (`min_sl_distance_pct` modul), biaya transaksi terukur
   `lux-research` (≈0,1225% pulang-pergi) menjadi ≈**0,306R per perdagangan**. Model biaya LTF
   harus dipatok dan diaudit sebelum run bergerbang mana pun.
