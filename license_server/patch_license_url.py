#!/usr/bin/env python3
"""Patch Diso binary license base URL (max 22 bytes, null-padded)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

OLD = b"https://flightmy.info/"
# default points at local Diso license server (same length as OLD = 22)
DEFAULT_NEW = b"http://127.0.0.1:7474/"

TARGETS = [
    Path(r"C:\Users\pnsto\Desktop\Diso\var\jb\Applications\Diso.app\Diso"),
    Path(r"C:\Users\pnsto\Desktop\Diso\Diso.app\Diso"),
]


def patch(path: Path, new_url: bytes) -> bool:
    if len(new_url) > len(OLD):
        raise SystemExit(f"URL too long ({len(new_url)} > {len(OLD)}): {new_url!r}")
    data = bytearray(path.read_bytes())
    # find current base URL candidates
    candidates = [OLD, DEFAULT_NEW]
    # also find whatever http(s) string is currently at known offset if present
    idx = data.find(OLD)
    if idx < 0:
        idx = data.find(DEFAULT_NEW)
    if idx < 0:
        # search any previous custom: look for check.php neighbor
        c = data.find(b"check.php")
        if c > 0:
            # walk back to previous C-string start
            j = c - 2
            while j > 0 and data[j] != 0:
                j -= 1
            start = j + 1
            cur = bytes(data[start:c])
            if cur.startswith(b"http"):
                idx = start
                candidates = [cur.rstrip(b"\x00")]
    if idx < 0:
        print("FAIL: license URL not found in", path)
        return False

    # determine length of existing C-string field (until NUL)
    end = idx
    while end < len(data) and data[end] != 0:
        end += 1
    field_len = end - idx
    if len(new_url) > field_len:
        raise SystemExit(f"URL longer than field ({field_len})")
    replacement = new_url + b"\x00" * (field_len - len(new_url))
    old_field = bytes(data[idx:end])
    data[idx:end] = replacement
    # keep terminating NUL
    assert data[end] == 0
    path.write_bytes(data)
    print(f"OK {path}")
    print(f"  offset 0x{idx:x}")
    print(f"  old: {old_field!r}")
    print(f"  new: {new_url!r} (+{field_len-len(new_url)} NUL pad)")
    print(f"  sha256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
    return True


def main():
    new = sys.argv[1].encode() if len(sys.argv) > 1 else DEFAULT_NEW
    if not new.endswith(b"/"):
        print("NOTE: URL should end with / because client appends check.php")
    ok = True
    for t in TARGETS:
        if not t.exists():
            print("SKIP missing", t)
            continue
        ok = patch(t, new) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
