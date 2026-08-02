#!/usr/bin/env python3
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

data = Path(__file__).resolve().parents[1] / "payload/var/jb/Applications/Diso.app/Diso"
data = data.read_bytes()
BASE = 0x100000000


def fix_ptr(p: int) -> int:
    p &= 0xFFFFFFFFF
    if p > 0x200000000:
        p = (p & 0xFFFFFFF) | BASE
    if p < BASE:
        p |= BASE
    return p


classlist_off = 0x6C298
classlist_size = 0x98
for i in range(0, classlist_size, 8):
    ptr = fix_ptr(struct.unpack_from("<Q", data, classlist_off + i)[0])
    foff = ptr - BASE
    data_ptr = fix_ptr(struct.unpack_from("<Q", data, foff + 32)[0])
    ro_off = data_ptr - BASE
    flags_ro = struct.unpack_from("<I", data, ro_off)[0]
    name_ptr = fix_ptr(struct.unpack_from("<Q", data, ro_off + 24)[0])
    if name_ptr - BASE >= len(data) or name_ptr < BASE:
        ro2 = fix_ptr(struct.unpack_from("<Q", data, ro_off + 8)[0])
        ro_off = ro2 - BASE
        name_ptr = fix_ptr(struct.unpack_from("<Q", data, ro_off + 24)[0])
    name = data[name_ptr - BASE : name_ptr - BASE + 80].split(b"\x00")[0]
    print(hex(ptr), name)
    if name != b"CITheme":
        continue
    base_methods = struct.unpack_from("<Q", data, ro_off + 32)[0]
    print(" baseMethods raw", hex(base_methods))
    if not base_methods:
        continue
    base_methods = fix_ptr(base_methods)
    mo = base_methods - BASE
    entsize_and_flags, count = struct.unpack_from("<II", data, mo)
    entsize = entsize_and_flags & 0xFFFC
    relative = bool(entsize_and_flags & 0x80000000)
    print(" entsize", entsize, "relative", relative, "count", count)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    for j in range(count):
        if relative or entsize == 12:
            ent = mo + 8 + j * 12
            no, to, io = struct.unpack_from("<iii", data, ent)
            nptr = ent + no
            iptr = ent + 8 + io
            ns = data[nptr : nptr + 80].split(b"\x00")[0].decode(errors="replace")
            print(f"  {ns:40s} imp_file={iptr:#x}")
            # disasm first 40 insns
            code = data[iptr : iptr + 160]
            for insn in md.disasm(code, BASE + iptr):
                print(f"    {insn.address:#x}: {insn.mnemonic} {insn.op_str}")
                if insn.address > BASE + iptr + 120:
                    break
        else:
            ent = mo + 8 + j * entsize
            n, t, imp = struct.unpack_from("<QQQ", data, ent)
            n = fix_ptr(n)
            ns = data[n - BASE : n - BASE + 80].split(b"\x00")[0]
            print(ns, hex(imp))


if __name__ == "__main__":
    pass
