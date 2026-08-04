#!/usr/bin/env python3
"""Simple setup (như lần trước):
- UI full black + soft text
- License: base URL http://127.0.0.1:7474/ + check.php
  Server local đọc Google Sheet (không cloud always-on)
"""
from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "payload/var/jb/Applications/Diso.app/Diso"

# Original cstring slot for license base (22 bytes max, classic)
LICENSE_CSTR = 0x4114D
LICENSE_FIELD = 22  # http://127.0.0.1:7474/ = 22
CF_LICENSE = 0x5B598  # isa, flags, ptr, length
CF_CHECK = 0x5A398

DEFAULT_URL = b"http://127.0.0.1:7474/"


def movz_w(rd: int, imm16: int) -> bytes:
    return (0x52800000 | ((imm16 & 0xFFFF) << 5) | (rd & 31)).to_bytes(4, "little")


def movk_w_lsl16(rd: int, imm16: int) -> bytes:
    return (0x72A00000 | ((imm16 & 0xFFFF) << 5) | (rd & 31)).to_bytes(4, "little")


def patch_rgb(data: bytearray, off: int, rgb: int) -> None:
    lo = rgb & 0xFFFF
    hi = (rgb >> 16) & 0xFFFF
    if off == 0x6FCC:
        data[off : off + 4] = movz_w(2, lo)
        return
    data[off : off + 8] = movz_w(2, lo) + movk_w_lsl16(2, hi)


def main() -> None:
    data = bytearray(APP.read_bytes())
    bak = APP.with_suffix(APP.suffix + ".pre-simple.bak")
    if not bak.exists():
        bak.write_bytes(bytes(data))
        print("backup", bak)

    # --- UI: full black + soft text ---
    colors = {
        0x6F90: 0x000000,  # bg
        0x6FA8: 0xE5E5EA,  # primary text (not pure white)
        0x6FB4: 0x8E8E93,  # secondary
        0x6FC0: 0xFF9F0A,  # orange
        0x6FCC: 0x00D2FF,  # soft blue (low-16)
        0x6FD4: 0x2C2C2E,  # separator
        0x6FE0: 0x000000,  # elevated black
        0x6FEC: 0x30D158,  # green
        0x6FF8: 0xFF453A,  # red
    }
    for off, rgb in colors.items():
        patch_rgb(data, off, rgb)
    print("UI: full black + soft text colors")

    # --- License classic: base URL + check.php ---
    # Restore check.php CFString length
    struct.pack_into("<Q", data, CF_CHECK + 24, 9)
    print("check.php suffix restored (len=9)")

    # Write classic short URL into original cstring slot
    url = DEFAULT_URL
    if len(url) > LICENSE_FIELD:
        raise SystemExit("URL too long")
    # clear field then write
    data[LICENSE_CSTR : LICENSE_CSTR + LICENSE_FIELD + 1] = b"\x00" * (LICENSE_FIELD + 1)
    data[LICENSE_CSTR : LICENSE_CSTR + len(url)] = url

    # Point CFString back to original slot
    new_ptr = 0x20000000000000 | LICENSE_CSTR
    struct.pack_into("<Q", data, CF_LICENSE + 16, new_ptr)
    struct.pack_into("<Q", data, CF_LICENSE + 24, len(url))
    print(f"license base URL -> {url.decode()!r} (app appends check.php)")

    # Clear free-space long URL slot if previously used
    data[0x54954 : 0x54954 + 200] = b"\x00" * 200

    APP.write_bytes(data)
    print("Wrote", APP)


if __name__ == "__main__":
    main()
