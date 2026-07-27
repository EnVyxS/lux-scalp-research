"""Lapisan sinyal jalur scalp.

Dua jenis berkas hidup di sini, dan keduanya tidak boleh tercampur:

- **Berkas terangkat** — salinan **byte-identik** dari modul `bot_v8`. Tidak satu
  karakter pun boleh berubah, termasuk komentar, spasi, dan nama variabel dalam
  bahasa aslinya. Kesetiaannya ditegakkan oleh `sumber.py` +
  `tests/test_sumber_pola.py`, bukan oleh niat baik.
- **Adaptor** — kode baru yang memanggil berkas terangkat. Di sinilah seluruh
  penyesuaian tinggal.

Alasan pemisahan ini: mengangkat-sambil-menyesuaikan adalah cara paling mudah
mengubah detektor tanpa menyadarinya, dan detektor yang berubah membuat hasil uji
tidak lagi berbicara tentang modul yang dikirim operator.
"""
