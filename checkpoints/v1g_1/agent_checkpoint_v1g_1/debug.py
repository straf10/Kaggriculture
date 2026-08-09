"""Debug-only structured receipts (review_89d99f0_2026-08-05.md H4/G11). Off by default (guards.debug=False);
harness.play already parses stdout lines with this prefix into `PlayResult.diagnostics`."""
import json

from .config import CONFIG

RECEIPT_PREFIX = "KAGGRI_RECEIPT "


def emit_receipt(payload: dict) -> None:
    if not CONFIG["guards"].get("debug", False):
        return
    print(RECEIPT_PREFIX + json.dumps(payload, sort_keys=True))
