# Manuflow ERP

Fondasi ERP manufaktur multi-platform untuk web dan Android. Frontend menggunakan Flutter, API menggunakan FastAPI, dan data disimpan di PostgreSQL.

Modul awal yang sudah tersedia:

- Login menggunakan email dan password
- Manajemen user: list responsif, pagination/filter, detail, tambah, update, dan soft-delete dengan modal konfirmasi
- Tampilan responsif: tabel dan sidebar di desktop, kartu dan drawer di mobile
- ID user otomatis dengan format `ddMMyyNNN`, contoh `080826000`; urutan kembali ke `000` setiap hari
- Master Data Corporation, Product, Machine, dan Plant dengan list responsif, pagination, filter name/code, detail, create, update, serta delete confirmation
- Master Data Department dengan PIC dan Head yang dipilih dari User aktif
- Kode Corporation/Product/Machine berbasis inisial yang unik (`ABC`, `ABC001`, dan seterusnya); Plant memakai kode acak alfanumerik 5 karakter
- Access level terpisah untuk Staff, Head, dan Administrator: Staff submit, Head mengelola data department sendiri, Administrator memiliki akses penuh
- Product memiliki satu customer dan satu supplier (boleh Corporation yang sama) serta menyimpan gross/nett weight secara presisi dalam gram
- User dapat mengganti password sendiri dari sidebar dengan verifikasi password saat ini
- Purchasing/Purchase Order dengan form multi-item, quantity gram, snapshot supplier/product/plant, kalkulasi IDR, pagination/filter, dan detail responsif
- Akses Purchasing hanya untuk PIC atau Head Department berkode `PURCHASING`; middleware API dan Flutter page guard memeriksa ulang akses sebelum halaman ditampilkan
- PO dibuat sebagai `waiting_review`; PIC/Head dapat edit/delete sebelum review, hanya Head dapat approve/reject, dan hasil review menjadi read-only
- Sales Order multi-item dengan Customer PO, Bill To/Ship To snapshot, quantity gram, harga IDR, dan Order Type Regular/Sample/Trial/Replacement
- Akses Sales Order hanya untuk PIC atau Head Department berkode `SALES`, menggunakan middleware API dan Flutter page guard; hanya Head dapat approve/reject
- Receiving untuk seluruh user aktif Department `WAREHOUSE`, dengan Product Lot unik, quantity gram, Storage Location per Plant, inventory ledger, dan saldo Product agregat seluruh Lot
- Receiving langsung Posted dan read-only; PIC/Head Warehouse dapat melakukan reversal yang tercatat sebagai movement terpisah dan tidak boleh menyebabkan stok negatif

Menu untuk Sales Order, Receiving, Warehouse, Production, Quality, Finish Good, Delivery, Dashboard, dan Reporting sudah disiapkan sebagai navigasi untuk tahap berikutnya.

Setelah migrasi, buka Master Data → Department dan tetapkan PIC serta Head pada Department `PURCHASING`. Menu Purchasing baru muncul untuk kedua user tersebut.
Lakukan langkah yang sama pada Department `SALES` agar menu Sales Order tersedia untuk PIC dan Head Sales.
Untuk Receiving, tetapkan user ke Department `WAREHOUSE`; PIC/Head Warehouse memiliki hak reversal. Buat Storage Location pada Master Data sebelum mencatat penerimaan.

## Menjalankan backend

Salin konfigurasi contoh lalu hidupkan PostgreSQL dan API:

```bash
cp .env.example .env
docker compose up --build
```

API tersedia di `http://localhost:8000`, dokumentasi interaktif di `http://localhost:8000/docs`. Saat pertama dijalankan, akun admin development otomatis dibuat dari nilai `FIRST_ADMIN_*` di `.env` (default `admin@example.com` / `Admin123!`). Ganti kredensial dan `JWT_SECRET` sebelum deployment.

## Menjalankan Flutter

```bash
cd frontend
flutter pub get
flutter run -d chrome --web-port 3000
```

Untuk emulator Android:

```bash
flutter run -d android
```

Alamat API default adalah `localhost:8000` untuk web dan `10.0.2.2:8000` untuk emulator Android. Untuk perangkat fisik atau environment lain, berikan alamat API:

```bash
flutter run --dart-define=API_URL=http://192.168.1.10:8000/api/v1
```

## Pengembangan backend tanpa Docker API

PostgreSQL tetap dapat dijalankan dari Docker, sedangkan API dijalankan lokal:

```bash
docker compose up -d db
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.scripts.seed_admin
uvicorn app.main:app --reload
```

## Pemeriksaan

```bash
cd backend && pytest && ruff check .
cd frontend && flutter analyze && flutter test
```

Catatan keamanan: `android:usesCleartextTraffic` aktif agar development lokal melalui HTTP mudah dilakukan. Gunakan HTTPS dan matikan opsi tersebut pada build production.
