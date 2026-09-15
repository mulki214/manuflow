# Version control dan promosi environment

## Cabang tetap

| Cabang | Fungsi | Environment |
| --- | --- | --- |
| `local` | Integrasi perubahan yang telah direview dan diuji di mesin pengembang | Local |
| `staging` | Kandidat rilis yang telah lolos pengujian local | Staging |
| `main` | Kode yang sedang/siap berjalan di production | Production |

`main` dipertahankan sebagai cabang production karena deployment yang sudah ada memakai cabang tersebut. Tidak ada perubahan aplikasi langsung pada tiga cabang tetap ini.

## Membuat perbaikan atau fitur

1. Mulai dari `local` yang terbaru.
2. Buat cabang terpisah: `fix/<ringkasan>` untuk bug, `feature/<ringkasan>` untuk fitur, atau `chore/<ringkasan>` untuk konfigurasi/maintenance.
3. Lakukan perubahan kecil dengan commit Conventional Commits, misalnya `fix(receiving): show outstanding PO items`.
4. Jalankan pemeriksaan yang relevan dan buka pull request ke `local`.
5. Setelah local disetujui, promosikan `local` ke `staging` melalui pull request dan deploy ke staging.
6. Setelah staging disetujui, promosikan `staging` ke `main`, buat tag rilis, lalu deploy production.

## Aturan rilis

- Tidak boleh direct push ke `local`, `staging`, atau `main`.
- Setiap pull request mencantumkan dampak database/migrasi, API, dan frontend bila ada.
- Migration Alembic harus kompatibel saat upgrade; tidak boleh menghapus data tanpa rencana rollback.
- Gunakan tag SemVer pada commit production, contoh `v1.2.0`; hotfix produksi menggunakan `v1.2.1`.
- Hotfix kritis boleh dimulai dari `main` sebagai `hotfix/<ringkasan>`, kemudian harus dimasukkan kembali ke `staging` dan `local` setelah rilis.

## Perintah sehari-hari

```bash
git switch local
git pull origin local
git switch -c fix/nama-perbaikan

# setelah perubahan dan test
git add <file-yang-diubah>
git commit -m "fix(area): ringkasan"
git push -u origin fix/nama-perbaikan
```

Promosi dilakukan melalui pull request GitHub agar review, status test, dan riwayat rilis tetap terbaca.
