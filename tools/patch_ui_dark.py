#!/usr/bin/env python3
"""Patch Diso binary: dark theme colors, clearer button accent, remove contact/Telegram promo."""
from __future__ import annotations

from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "payload/var/jb/Applications/Diso.app/Diso"


def movz_w(rd: int, imm16: int) -> bytes:
    return (0x52800000 | ((imm16 & 0xFFFF) << 5) | (rd & 31)).to_bytes(4, "little")


def movk_w_lsl16(rd: int, imm16: int) -> bytes:
    return (0x72A00000 | ((imm16 & 0xFFFF) << 5) | (rd & 31)).to_bytes(4, "little")


def rgb_mov_pair(rgb: int) -> bytes:
    """Encode mov w2, #lo + movk w2, #hi, lsl#16 for 0x00RRGGBB."""
    lo = rgb & 0xFFFF
    hi = (rgb >> 16) & 0xFFFF
    return movz_w(2, lo) + movk_w_lsl16(2, hi)


def patch_rgb(data: bytearray, off: int, new_rgb: int, old_rgb: int | None = None) -> None:
    if old_rgb is not None:
        cur = int.from_bytes(data[off : off + 4], "little")
        # just verify first mov exists
    pair = rgb_mov_pair(new_rgb)
    # For colors that use only movz (hi==0), second insn may be plain b not movk
    if (new_rgb >> 16) == 0:
        # only patch first instruction lower 16 — keep following as-is if it's b
        data[off : off + 4] = movz_w(2, new_rgb & 0xFFFF)
    else:
        data[off : off + 8] = pair


def pad_utf16(new: str, old_bytes: bytes) -> bytes:
    """Replace UTF-16LE string keeping same byte length (NUL pad)."""
    nb = new.encode("utf-16le")
    if len(nb) > len(old_bytes):
        raise ValueError(f"new string too long: {len(nb)} > {len(old_bytes)} for {new!r}")
    return nb + b"\x00" * (len(old_bytes) - len(nb))


def pad_ascii(new: str, old: bytes) -> bytes:
    b = new.encode("ascii")
    if len(b) > len(old):
        raise ValueError(f"ascii too long {new!r}")
    return b + b"\x00" * (len(old) - len(b))


def main() -> None:
    raw = bytearray(APP.read_bytes())
    # backup once
    bak = APP.with_suffix(APP.suffix + ".pre-dark.bak")
    if not bak.exists():
        bak.write_bytes(raw)

    # --- CITheme color immediates (file offsets = vm - 0x100000000 for low addrs in __text) ---
    # 0x6f90: bg light F2F3F5 -> dark bg 1C1C1E
    patch_rgb(raw, 0x6F90, 0x1C1C1E)
    # 0x6fa8: was dark label 1C1C1E -> light text F2F2F7 (readable on dark)
    patch_rgb(raw, 0x6FA8, 0xF2F2F7)
    # 0x6fb4: secondary gray 8E8E93 -> brighter secondary AEAEB2
    patch_rgb(raw, 0x6FB4, 0xAEAEB2)
    # 0x6fc0: orange FF9500 -> keep, slightly brighter FFA00A
    patch_rgb(raw, 0x6FC0, 0xFF9F0A)
    # 0x6fcc: blue 007AFF (only movz) -> 0A84FF dark-mode blue
    # needs mov + movk (was only mov because hi=0)
    raw[0x6FCC : 0x6FCC + 4] = movz_w(2, 0x84FF)
    # next insn is `b #...` — cannot insert movk without shifting. Keep 007AFF or use 0x0AFF-ish
    # 0x7AFF is fine system blue; for brighter use 0x84FF still upper 0 -> 0x000084FF close enough
    raw[0x6FCC : 0x6FCC + 4] = movz_w(2, 0x84FF)
    # 0x6fd4: E5E5EA light sep -> 3A3A3C dark sep
    patch_rgb(raw, 0x6FD4, 0x3A3A3C)
    # 0x6fe0: D1D1D6 light fill -> 2C2C2E dark elevated
    patch_rgb(raw, 0x6FE0, 0x2C2C2E)
    # 0x6fec green 34C759 -> 30D158 (dark mode green)
    patch_rgb(raw, 0x6FEC, 0x30D158)
    # 0x6ff8 red FF3B30 -> FF453A
    patch_rgb(raw, 0x6FF8, 0xFF453A)

    # --- Remove contact / Telegram promo (same length) ---
    patches_u16 = [
        (
            0x4F1AE,
            "Máy: %@\nLiên hệ Telegram @houselis để mua key",
            "Máy: %@\nNhập key hợp lệ để kích hoạt.",
        ),
        (
            0x51DCA,
            "Không thể Change Device. Vui lòng gia hạn key (Telegram @houselis).",
            "Không thể Change Device. Vui lòng kiểm tra hoặc gia hạn key.",
        ),
    ]
    for off, old, new in patches_u16:
        old_b = old.encode("utf-16le")
        assert raw[off : off + len(old_b)] == old_b, (hex(off), raw[off : off + len(old_b)])
        raw[off : off + len(old_b)] = pad_utf16(new, old_b)

    # ascii menu/label
    off = 0x42709
    old = b"telegram: Houselis"
    assert raw[off : off + len(old)] == old
    raw[off : off + len(old)] = pad_ascii("Diso Support", old)

    # Brand strings if still HIOS in title area
    for old, new in [(b"HIOS Faker v3", b"Diso\x00\x00\x00\x00\x00\x00\x00\x00\x00"), (b"HIOS Faker", b"Diso\x00\x00\x00\x00\x00\x00")]:
        p = raw.find(old)
        if p >= 0 and len(new) == len(old):
            raw[p : p + len(old)] = new
            print(f"brand patch at {p:#x}")

    APP.write_bytes(raw)
    print("Patched", APP)
    print("Size", len(raw))
    # show color slots
    for off, label in [
        (0x6F90, "bg"),
        (0x6FA8, "label"),
        (0x6FB4, "secondary"),
        (0x6FC0, "orange"),
        (0x6FCC, "blue"),
        (0x6FD4, "sep"),
        (0x6FE0, "elevated"),
        (0x6FEC, "green"),
        (0x6FF8, "red"),
    ]:
        lo = int.from_bytes(raw[off : off + 4], "little")
        print(hex(off), label, hex(lo))


if __name__ == "__main__":
    main()
