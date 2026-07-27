# ADR-S006 — Cacat 24, aturan status putaran, pagar teks, dan kontrak pengangkatan berkas

- Status: DITERIMA
- Tanggal: 2026-07-28
- Repositori: `lux-scalp-research`
- HEAD saat ditulis: `283552a59f96a98f7e935cdf82c551fc49e59e40`
- Menggantikan: tidak ada. Melengkapi ADR-S001 §debt, ADR-S005 §8.

ADR ini memindahkan tiga temuan yang sebelumnya hanya hidup di jurnal ke dalam
keputusan yang mengikat, lalu menambah satu kontrak baru yang lahir dari fakta
yang baru terukur hari ini.

---

## §1 Cacat 24 — "cache tanpa manifes"

Empat putaran CI pertama di repositori ini (`probe-ltf #1`, `tests #1..#3`) mati
di 6–18 detik. Penyebabnya bukan pytest dan bukan kode uji: `actions/setup-python@v5`
dengan `cache: 'pip'` mencari `**/requirements.txt` atau `**/pyproject.toml`.
Tidak ada satu pun di akar repositori, sehingga langkah itu **gagal keras**,
sebelum `pip install`, jauh sebelum pytest dijalankan.

Bukti kausal (bukan korelasi): commit `72e5b57dfe1b9ff80f7a3c93dc079c47488c865a`
hanya menambah `requirements.txt` dan satu berkas uji. Ia **tidak** mengubah
`tests.yml` dan tidak mengubah satu pun uji yang sudah ada. Alur sama, kode sama,
satu variabel berubah. Sebelum: merah di 6–18 s. Sesudah: hijau, pytest 0,09 s.
Ini satu-satunya eksperimen satu-variabel terkendali yang pernah dijalankan di
repositori ini, dan yang memaksanya adalah operator, bukan saya.

**Keputusan.** `cache: 'pip'` hanya boleh ada di sebuah alur bila ada manifes
dependensi di akar repositori. Ditegakkan oleh `tests/test_kebutuhan_pip.py`
(9 butir, berakar di `Path(__file__).resolve().parents[1]`, bukan CWD).

**Asal cacat:** menyalin konvensi dari `lux-research` sepotong-sepotong —
mengambil `cache: 'pip'` tanpa mengambil `requirements.txt` yang menghalalkannya.

---

## §2 Aturan status putaran CI (calon aturan 71)

Saya mendorong tiga commit pemicu CI (`3087f3c7`, `470b3f91`, `1d9b1144`) dan
mempra-registrasi R-Y13 di atasnya, tanpa pernah memastikan satu putaran hijau.
Operator yang menemukan kegagalannya. Ini sekelas cacat 22.

**Keputusan.** Setiap commit yang memicu CI wajib dinyatakan salah satu dari:

1. **hijau** — dengan kutipan dari `reports/tests.md` (commit + cacah + kode keluar);
2. **merah** — dengan kutipan baris `FAILED`/`ERROR`;
3. **belum diketahui** — bila laporannya belum ada.

"belum diketahui" **tidak pernah** boleh dihitung sebagai kemajuan, dan tidak boleh
dipakai sebagai landasan pra-registrasi ramalan berikutnya.

Celah yang memungkinkan kesalahan ini: 15 pagar di `tests/test_workflow_tests_yml.py`
menguji **teks** `tests.yml`, bukan bahwa alurnya **berjalan**. Tidak ada pagar teks
yang bisa menangkap kegagalan lingkungan; hanya putaran hijau yang bisa.

---

## §3 Pagar berbasis teks tidak dapat membedakan direktif dari komentar tentang direktif (calon aturan 72)

Commit `636b5943` merah karena satu sebab yang tidak saya ramalkan:
`assert isi.count("cache: 'pip'") == 1` melihat **2**, sebab komentar penjelas yang
saya tambahkan di atas blok `setup-python` memuat literal itu di dalam backtick.
Pytest berjalan 0,10 s, 77 butir lain lulus. Penyebabnya komentar saya sendiri.

Dua jalan keluar ada; saya memilih yang kedua dan **menolak** yang pertama:

- melunakkan pagar (mis. menghitung hanya baris non-komentar) — **DITOLAK**. Ini pola
  yang sama dengan melunakkan ambang supaya sebuah hipotesis lulus.
- menulis ulang komentar sehingga ia memperingatkan penyunting berikutnya **tanpa**
  menuliskan literal yang dipagari. Dilakukan di `97fb2878`, blob `4450c91a…`.

**Keputusan.** Jangan pernah menuliskan literal yang dipagari di dalam komentar pada
berkas yang dipagari. Membaca pagar secara verbatim sebelum menyunting adalah perlu
tetapi tidak cukup: yang saya lakukan salah karena saya menalar tentang **maksud**
pagar, bukan tentang **cara ia mengukur**.

---

## §4 Verifikasi sebelum dorong (calon aturan 73)

Sandbox tidak punya pytest dan tidak punya jaringan, jadi pagar tidak bisa dijalankan
sebelum didorong. Tetapi **identitas byte bisa**. Prosedur yang menghasilkan R-Y16:

1. baca berkas sumber dari sandbox (`sed -n`), utuh;
2. rakit kandidat dengan `computer.writeFile`;
3. buktikan lokal: `cmp -s`, `sha256sum`, `git hash-object` — `git hash-object`
   menghasilkan angka yang sama dengan blob SHA GitHub;
4. baru dorong; lalu **baca ulang dari `main`** dan bandingkan blob yang dikembalikan.

**Keputusan.** Untuk setiap pengangkatan berkas, langkah 3 wajib mendahului langkah 4.
Ukuran berkas saja tetap bukan bukti; blob yang cocok adalah bukti.

---

## §5 Kontrak pengangkatan dua tingkat

Fakta baru yang terukur hari ini: `strategy.py:51` memuat `import patterns` —
impor **absolut**, dan `patterns.` dirujuk **14 kali** di dalam berkas itu.
Di `lux_ltf/sinyal/` tidak ada modul tingkat-atas bernama `patterns`; hasil angkatannya
bernama `pola_v9.py`. Maka pengangkatan setia-penuh `strategy.py` **mustahil**:
berkasnya akan mengimpor modul yang tidak ada.

Karena itu kontrak pengangkatan dipecah menjadi dua tingkat:

**Tingkat A — setia penuh.** Berkas hasil angkatan byte-identik dengan sumbernya.
Diuji dengan pembandingan blob. Berlaku untuk `patterns.py -> pola_v9.py`
(blob `9ff67d554317c5a28d6a1e092b57988f76a97e65`, sudah terbukti).

**Tingkat B — setia dengan deviasi terdeklarasi.** Berkas hasil angkatan sama dengan
sumbernya **kecuali** sejumlah baris yang didaftarkan satu per satu di dalam ADR,
sebelum pengangkatan. Deviasi hanya boleh bersifat mekanis pada jalur impor —
tidak boleh menyentuh logika, ambang, atau angka apa pun.

Deviasi yang disahkan untuk `strategy.py -> lux_ltf/sinyal/sweep_v9.py`, tepat satu baris:

```
51c51
< import patterns
---
> from . import pola_v9 as patterns
```

Angka target, diukur di sandbox sebelum pengangkatan:

| besaran | `strategy.py` (sumber) | `sweep_v9.py` (target) |
|---|---|---|
| byte | 70.020 | **70.038** |
| baris | 1.598 | 1.598 |
| baris berbeda | — | **1** |
| blob git | `528d5591a072a4b6c225163e5b0019e053b417bd` | **`2f3909494ce26681789d0818ddd49172bea21bda`** |
| sha256 | `8623eaaf700618c1633db02add491a7b45d21d03d4e94482fc180b30447b0ae4` | `d0bd2ea593375bb82bbdf91d926fb5dabb7c914d24834c77a9f8a2d7aa73bfe0` |

Karena angka target dipatok **sebelum** pengangkatan, tingkat B tetap dapat difalsifikasi
sekeras tingkat A: blob yang dikembalikan GitHub harus `2f390949…`, bukan angka lain.

`engine.py` tetap **sengaja tidak diangkat** (ADR-S003/S004): lapisan entry/SL/TP-nya
akan ditulis ulang sebagai adaptor, bukan disalin.

---

## §6 Utang yang ditinggalkan sengaja

1. `lux_ltf/sinyal/sumber.py` belum mengenal deviasi terdeklarasi. `periksa_berkas`
   hanya bisa menyatakan setia/tidak setia terhadap blob sumber. Perlu jalur kedua:
   berkas tingkat B dibandingkan dengan blob **target**, bukan blob sumber. Sunting
   ini menyentuh berkas berpagar dan wajib mengikuti §4.
2. `tests/test_workflow_tests_yml.py` masih membaca jalur relatif-CWD
   (`JALUR = Path(".github/workflows/tests.yml")`). Bukan pelunakan bila diubah ke
   `parents[1]`; ini perbaikan ketegaran. Commit tersendiri.
3. `probe_ltf.yml` belum pernah dijalankan ulang sejak cacat 24 disembuhkan. Ia hanya
   terpicu oleh `lux_ltf/probe_arsip.py` atau berkasnya sendiri, dan tidak ada satu pun
   commit saya menyentuh keduanya. Perlu **tindakan operator**: Actions -> `probe-ltf`
   -> Run workflow di `main`. Tanpa angka byte dari probe, saya tidak bisa memutuskan
   apakah serapan 12 simbol muat di pagu 6 jam (R-Y12, R-Y15).

---

## §7 Papan skor dan pra-registrasi

Diadjudikasi di ADR ini: **R-Y16 TEPAT**, **R-Y18 TEPAT**. Rincian kutipan ada di
`journal/2026-07-28-03.md`.

Dipra-registrasi di sini, sebelum dijalankan:

- **R-Y19.** `sweep_v9.py` didorong pada percobaan pertama dan blob yang dikembalikan
  GitHub adalah `2f3909494ce26681789d0818ddd49172bea21bda` (70.038 B, 1.598 baris).
  Ini taruhan pada prosedur §4 pada berkas 2,2x lebih besar dari `pola_v9.py`.
- **R-Y20.** Putaran CI atas commit itu hijau dengan cacah **tetap 79** dan 0 dilewati,
  sebab belum ada uji baru yang menguji `sweep_v9.py`. Bila cacahnya berubah tanpa saya
  menambah uji, ada sesuatu yang saya tidak pahami tentang pengumpulan pytest.
- **R-Y21.** Ketika `sumber.py` diperluas untuk deviasi terdeklarasi, `import`
  relatif `from . import pola_v9 as patterns` bekerja apa adanya karena `lux_ltf/sinyal/`
  punya `__init__.py`; tidak diperlukan sisipan `sys.path` mana pun.
