# Uji — lux-scalp-research

- commit: 636b5943dc2cbd7dc6e7cca5e34395345098ebbc
- Butir terkumpul: 79
- Kode keluar kumpul: 0
- Kode keluar pytest: 1

## Baris FAILED/ERROR (tidak dipotong)

```
FAILED tests/test_workflow_tests_yml.py::test_cache_pip_sudah_ada_dan_tunggal - assert 2 == 1
```

## Ekor keluaran (200 baris)

```
..............................................................s......... [ 91%]
....F..                                                                  [100%]
=================================== FAILURES ===================================
_____________________ test_cache_pip_sudah_ada_dan_tunggal _____________________
tests/test_workflow_tests_yml.py:86: in test_cache_pip_sudah_ada_dan_tunggal
    assert isi.count("cache: 'pip'") == 1
E   assert 2 == 1
E    +  where 2 = <built-in method count of str object at 0x55d480700c60>("cache: 'pip'")
E    +    where <built-in method count of str object at 0x55d480700c60> = 'name: tests\n\non:\n  push:\n    paths:\n      - \'lux_ltf/**\'\n      - \'tests/**\'\n      - \'.github/workflows/te...            echo "pytest gagal dengan kode ${KODE}"\n            exit 1\n          fi\n          echo "pytest hijau"\n'.count
=========================== short test summary info ============================
FAILED tests/test_workflow_tests_yml.py::test_cache_pip_sudah_ada_dan_tunggal - assert 2 == 1
 +  where 2 = <built-in method count of str object at 0x55d480700c60>("cache: 'pip'")
 +    where <built-in method count of str object at 0x55d480700c60> = 'name: tests\n\non:\n  push:\n    paths:\n      - \'lux_ltf/**\'\n      - \'tests/**\'\n      - \'.github/workflows/te...            echo "pytest gagal dengan kode ${KODE}"\n            exit 1\n          fi\n          echo "pytest hijau"\n'.count
1 failed, 77 passed, 1 skipped in 0.10s
```
