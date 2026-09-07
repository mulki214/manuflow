"""Deterministic parser for product and lot QR identities."""

import json
from urllib.parse import parse_qs


def parse_product_qr(payload: str) -> tuple[str, str | None]:
    """Accept product code, JSON, query-string, or MANUFLOW|PRODUCT|LOT."""
    value = payload.strip()
    if not value:
        raise ValueError("QR payload is empty")
    if value.startswith("{"):
        data = json.loads(value)
        code = str(data.get("product_code", "")).strip()
        lot = str(data.get("lot_number", "")).strip() or None
    elif "=" in value:
        data = parse_qs(value)
        code = data.get("product_code", [""])[0].strip()
        lot = data.get("lot_number", [""])[0].strip() or None
    elif value.startswith("MANUFLOW|"):
        parts = value.split("|")
        if len(parts) not in (2, 3) or not parts[1].strip():
            raise ValueError("Invalid MANUFLOW product QR")
        code = parts[1].strip()
        lot = parts[2].strip() if len(parts) == 3 else None
    else:
        code, lot = value, None
    if not code:
        raise ValueError("QR does not contain a product code")
    return code, lot
