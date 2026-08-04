#!/usr/bin/env python3
"""Point Diso binary at a public full license URL (no same Wi‑Fi / no PC).

Uses free __TEXT padding + disables check.php append so full /exec URL fits.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "payload/var/jb/Applications/Diso.app/Diso"
ACTIVE = ROOT / "license_server" / "ACTIVE_URL.txt"
SLOT = 0x54954
CF_LICENSE = 0x5B598
CF_CHECK = 0x5A398


def main() -> None:
    url = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not url and ACTIVE.exists():
        for line in ACTIVE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                url = line
                break
    if not url:
        raise SystemExit("usage: set_public_license_url.py <https://.../exec>")

    raw = url.encode("ascii")
    if len(raw) + 1 > 200:
        raise SystemExit("URL too long")

    data = bytearray(APP.read_bytes())
    # disable check.php append — base is full endpoint
    struct.pack_into("<Q", data, CF_CHECK + 24, 0)
    data[SLOT : SLOT + 200] = b"\x00" * 200
    data[SLOT : SLOT + len(raw)] = raw
    struct.pack_into("<Q", data, CF_LICENSE + 16, 0x20000000000000 | SLOT)
    struct.pack_into("<Q", data, CF_LICENSE + 24, len(raw))
    APP.write_bytes(data)
    print("OK", url)
    print("check.php suffix len=0, full endpoint in binary")


if __name__ == "__main__":
    main()
