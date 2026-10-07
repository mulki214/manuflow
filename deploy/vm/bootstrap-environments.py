#!/usr/bin/env python3
"""Split the current production environment into staging and fresh production."""

from __future__ import annotations

import secrets
from pathlib import Path


ROOT = Path("/opt/manuflow")
OLD_ENV = ROOT / ".env.production"
SOURCE_ENV = ROOT / ".env.production.vm-original"
STAGING_ENV = ROOT / ".env.staging"
PRODUCTION_ENV = ROOT / ".env.production"
MARKER = ROOT / ".vm-environments-initialized"


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    content = "".join(f"{key}={value}\n" for key, value in values.items())
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content)
    temporary.chmod(0o600)
    temporary.replace(path)


def main() -> None:
    if MARKER.exists():
        raise SystemExit("Environment split already initialized; refusing to overwrite secrets.")
    if not SOURCE_ENV.exists():
        if not OLD_ENV.exists():
            raise SystemExit(f"Missing existing environment file: {OLD_ENV}")
        SOURCE_ENV.write_bytes(OLD_ENV.read_bytes())
        SOURCE_ENV.chmod(0o600)

    current = read_env(SOURCE_ENV)
    required = {"POSTGRES_PASSWORD", "JWT_SECRET", "FIRST_ADMIN_EMAIL", "FIRST_ADMIN_PASSWORD"}
    if missing := required - current.keys():
        raise SystemExit(f"Missing required variables in current environment: {', '.join(sorted(missing))}")

    # Preserve existing database credentials for the current database. The
    # previous production volume becomes staging without copying or resetting it.
    staging = dict(current)
    staging.update(
        {
            "DEPLOY_ENV": "staging",
            "POSTGRES_VOLUME": "manuflow_production_postgres_data",
            "API_URL": "https://api.103.93.134.27.nip.io/api/v1",
            "CORS_ORIGINS": '["https://erp.103.93.134.27.nip.io"]',
        }
    )
    write_env(STAGING_ENV, staging)

    production = dict(current)
    production.update(
        {
            "DEPLOY_ENV": "production",
            "POSTGRES_PASSWORD": secrets.token_hex(32),
            "POSTGRES_VOLUME": "manuflow_prod_postgres_data",
            "JWT_SECRET": secrets.token_hex(64),
            "FIRST_ADMIN_EMAIL": "admin@example.com",
            "FIRST_ADMIN_FIRST_NAME": "System",
            "FIRST_ADMIN_LAST_NAME": "Administrator",
            "API_URL": "https://ap.103.93.134.27.nip.io/api/v1",
            "CORS_ORIGINS": '["https://ep.103.93.134.27.nip.io"]',
        }
    )
    write_env(PRODUCTION_ENV, production)
    MARKER.write_text("initialized\n")
    MARKER.chmod(0o600)
    print("Staging and fresh production environments initialized; secrets were not printed.")


if __name__ == "__main__":
    main()
