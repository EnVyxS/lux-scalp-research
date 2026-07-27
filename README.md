# lux-scalp-research

Jalur riset **scalp / kerangka waktu rendah (LTF)** untuk LUX: klines **5m** dan **15m** pada USDT-perp.

Repo ini **sengaja terpisah** dari [`EnVyxS/lux-research`](https://github.com/EnVyxS/lux-research).

## Mengapa terpisah

`lux-research` memelihara satu ledger percobaan tunggal (`N_percobaan`, saat ini **21**) dan
seluruh papan skornya dikoreksi banyak-pembandingan terhadap ledger itu (Šidák pada N=21 =
**0,002442**). Menambahkan sebuah keluarga hipotesis baru dengan dataset berbeda ke dalam ledger
yang sama akan:

1. menaikkan `N_percobaan` dan memperketat ambang bagi hipotesis lama secara retroaktif;
2. mencampur uji berdaya sangat berbeda di bawah satu koreksi tunggal — cacat yang sudah
   tercatat di `lux-research` (H-001 berjalan dengan 9 gerbang, 40 simbol, 100 ulangan
   permutasi, 356 jendela; H-015 dengan 11 gerbang, 437 simbol, 300 ulangan, 4.083 jendela);
3. membuat perbandingan lintas horizon tampak sebanding padahal tidak — biaya funding pada
   holding hari tidak sepadan dengan biaya fee pada holding menit.

Karena itu jalur ini punya ledger sendiri, penomoran hipotesis sendiri (`H-S001`, `H-S002`, …),
dan `N_percobaan` sendiri.

## Apa yang diuji di sini

Hipotesis pertama berasal dari modul `LUX_Terminal_v9` milik pemilik proyek: satu strategi
gabungan dengan **trendline break** sebagai komponen dominan, ditambah 14 detektor pola lain,
ADX/DI, ekspansi volume, divergensi RSI/MACD, dan lapisan SMC/ICT (order block, FVG, IFVG,
equal level, bias HTF), dijalankan pada timeframe dasar **5m** dengan konteks 15m/1h/4h.

Dua batasan yang dipatok oleh pemilik proyek dan **wajib dihormati**:

- `backtest.py` di dalam modul itu **tidak dipakai** (dinyatakan tidak lengkap);
- hasil apa pun yang sudah tercatat di dalam modul itu **bukan bukti** dan tidak boleh dikutip.

Modul itu memasok **spesifikasi aturan**, bukan angka. Setiap angka harus dilahirkan ulang oleh
harness di repo ini.

## Jalan masuk kembali ke `lux-research`

Sebuah temuan dari repo ini hanya boleh dipindahkan ke `lux-research` bila **seluruhnya** benar:

1. hipotesisnya dipra-registrasi di `decisions/` **sebelum** angka pertama terlihat;
2. seluruh gerbang harness lulus, termasuk `invarian_risiko` dan `checksum`;
3. p ≤ ambang Šidák terhadap `N_percobaan` **repo ini**;
4. t > 3,0 (Harvey–Liu–Zhu);
5. PBO < 0,50 di atas matriks periode × konfigurasi yang nyata, bukan diinferensi;
6. DSR > 0,95;
7. ada sel **entri acak** dengan manajemen posisi identik, dan strateginya mengalahkannya.

Syarat ke-7 bukan formalitas. Di `lux-research`, H-015 sel A menghasilkan entri acak
**0,10723R** sementara strateginya **0,07903R** — entri acak menang. Jalur mana pun yang tidak
mengalahkan entri acak tidak layak dipindahkan.

## Status

Belum ada hipotesis yang dijalankan. Belum ada dataset. `N_percobaan` = **0**.

Langkah aktif: memverifikasi ketersediaan arsip 5m/15m (lihat `lux_ltf/probe_arsip.py`).
