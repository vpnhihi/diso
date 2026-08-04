#!/usr/bin/env python3
"""Fix license URL in binary (no BOM), restore CFString lengths, verify, rebuild not included."""
from __future__ import annotations

import json
import struct
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "payload/var/jb/Applications/Diso.app/Diso"
ACTIVE = ROOT / "license_server" / "ACTIVE_URL.txt"
SLOT = 0x54954
CF_LICENSE = 0x5B598  # isa, flags, ptr, length
CF_CHECK = 0x5A398


def main() -> None:
    url = ACTIVE.read_text(encoding="utf-8-sig").strip()  # strip BOM
    if not url.endswith("/"):
        url += "/"
    raw = url.encode("ascii")
    print("TARGET", url, "len", len(raw))

    data = bytearray(APP.read_bytes())

    # Dump CFString before
    print("BEFORE check flags/ptr/len", 
          hex(struct.unpack_from("<Q", data, CF_CHECK + 8)[0]),
          hex(struct.unpack_from("<Q", data, CF_CHECK + 16)[0]),
          struct.unpack_from("<Q", data, CF_CHECK + 24)[0])
    print("BEFORE lic  flags/ptr/len",
          hex(struct.unpack_from("<Q", data, CF_LICENSE + 8)[0]),
          hex(struct.unpack_from("<Q", data, CF_LICENSE + 16)[0]),
          struct.unpack_from("<Q", data, CF_LICENSE + 24)[0])

    # Write URL slot
    data[SLOT : SLOT + 200] = b"\x00" * 200
    data[SLOT : SLOT + len(raw)] = raw

    # CFString license -> slot
    struct.pack_into("<Q", data, CF_LICENSE + 8, 0x7C8)  # flags ASCII
    struct.pack_into("<Q", data, CF_LICENSE + 16, 0x20000000000000 | SLOT)
    struct.pack_into("<Q", data, CF_LICENSE + 24, len(raw))

    # CFString check.php length restore (cstring still at 0x4130b)
    cstr = data.find(b"check.php\x00")
    print("check.php cstr at", hex(cstr) if cstr >= 0 else None)
    if cstr < 0:
        raise SystemExit("check.php missing")
    struct.pack_into("<Q", data, CF_CHECK + 8, 0x7C8)
    struct.pack_into("<Q", data, CF_CHECK + 16, 0x20000000000000 | cstr)
    struct.pack_into("<Q", data, CF_CHECK + 24, 9)

    APP.write_bytes(data)

    data2 = APP.read_bytes()
    print("AFTER check len", struct.unpack_from("<Q", data2, CF_CHECK + 24)[0])
    print("AFTER lic len", struct.unpack_from("<Q", data2, CF_LICENSE + 24)[0])
    print("AFTER lic ptr", hex(struct.unpack_from("<Q", data2, CF_LICENSE + 16)[0]))
    end = data2.index(0, SLOT)
    got = data2[SLOT:end]
    print("AFTER url", got)
    assert got == raw
    assert struct.unpack_from("<Q", data2, CF_CHECK + 24)[0] == 9
    assert struct.unpack_from("<Q", data2, CF_LICENSE + 24)[0] == len(raw)

    # Live API
    pub = url.rstrip("/")
    class NR(urllib.request.HTTPErrorProcessor):
        def http_response(self, req, resp):
            return resp
        https_response = http_response

    op = urllib.request.build_opener(NR)
    body = urllib.parse.urlencode(
        {
            "key": "666",
            "udid": "aab871f92fafbb561e847c96ea95553cc90769a71f9931e7cebc84e7a0d6a862",
            "nonce": "v1",
            "ts": str(int(time.time())),
        }
    ).encode()
    req = urllib.request.Request(
        pub + "/check.php",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "HIOSFaker/4.0",
        },
    )
    r = op.open(req, timeout=30)
    resp = r.read().decode()
    print("API", r.status, resp)
    j = json.loads(resp)
    assert r.status == 200 and j.get("ok") is True and j.get("status") == "ok"
    print("ALL_OK")


if __name__ == "__main__":
    main()
