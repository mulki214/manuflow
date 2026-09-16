# Android APK releases

The Android app has two release flavors that use the same signed codebase but
different package identities and APIs. Both may be installed on one device.

| Flavor | App name | Package | API |
| --- | --- | --- | --- |
| `staging` | Manuflow Staging | `com.erpmanufaktur.erp_manufaktur.staging` | Render staging API |
| `production` | Manuflow | `com.erpmanufaktur.erp_manufaktur` | Production API |

## Signing material

`frontend/android/key.properties` and the referenced keystore are intentionally
ignored by Git. Back them up securely before distributing a production APK.
Without the same keystore, future Android updates cannot be installed over an
existing production app.

Create `key.properties` by copying `key.properties.example` and use a private
keystore file at the configured path.

## Build commands

Run from `frontend/`:

```bash
flutter build apk --release --flavor staging \
  --dart-define=API_URL=https://manuflow-api.onrender.com/api/v1 \
  --build-name=1.0.0 --build-number=2

flutter build apk --release --flavor production \
  --dart-define=API_URL=https://api.103.93.134.27.nip.io/api/v1 \
  --build-name=1.0.0 --build-number=2
```

Artifacts are written under `build/app/outputs/flutter-apk/`. Upload each APK
as a separate asset on a GitHub Release; do not commit APKs to the repository.
