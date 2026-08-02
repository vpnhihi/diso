#!/usr/bin/env python3
"""Build Diso + dependency meta-packages and the Sileo APT repo (docs/).

- Fixes Windows backslash paths in data.tar
- Adds ellekit + mobilesubstrate meta .debs so Depends can be satisfied from this repo
- Rebuilds Packages / Release (flat + dists)
"""
from __future__ import annotations

import bz2
import gzip
import hashlib
import io
import lzma
import shutil
import struct
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
RELEASE_DIR = ROOT / "release"
DOCS = ROOT / "docs"
ARCH = "iphoneos-arm64"


def sha_all(data: bytes) -> tuple[str, str, str]:
    return (
        hashlib.md5(data).hexdigest(),
        hashlib.sha1(data).hexdigest(),
        hashlib.sha256(data).hexdigest(),
    )


def ar_write(path: Path, members: list[tuple[str, bytes]]) -> None:
    """Write a System V ar archive (.deb)."""
    out = bytearray(b"!<arch>\n")
    for name, data in members:
        # ar header: name(16) mtime(12) uid(6) gid(6) mode(8) size(10) magic(2)
        name_field = name.encode("ascii")
        if len(name_field) > 16:
            raise ValueError(f"ar member name too long: {name}")
        header = (
            name_field.ljust(16)
            + b"0".ljust(12)  # mtime
            + b"0".ljust(6)  # uid
            + b"0".ljust(6)  # gid
            + b"100644".ljust(8)
            + str(len(data)).encode("ascii").ljust(10)
            + b"`\n"
        )
        out.extend(header)
        out.extend(data)
        if len(data) % 2 == 1:
            out.append(0x0A)
    path.write_bytes(bytes(out))


def tar_xz_from_files(files: list[tuple[str, bytes, int]], dirs: list[str]) -> bytes:
    """Create ustar tar.xz. Paths must use forward slashes, no leading slash."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        # directories first
        for d in sorted(set(dirs)):
            d = d.strip("/").replace("\\", "/")
            if not d:
                continue
            info = tarfile.TarInfo(name=d)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "wheel"
            tf.addfile(info)
        for name, data, mode in files:
            name = name.strip("/").replace("\\", "/")
            info = tarfile.TarInfo(name=name)
            info.type = tarfile.REGTYPE
            info.size = len(data)
            info.mode = mode
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "wheel"
            tf.addfile(info, io.BytesIO(data))
    return lzma.compress(buf.getvalue(), preset=9)


def build_deb(control: str, postinst: str | None, data_files: list[tuple[str, bytes, int]], data_dirs: list[str], out_path: Path) -> bytes:
    control_files = [("control", control.encode("utf-8"), 0o644)]
    if postinst:
        control_files.append(("postinst", postinst.encode("utf-8").replace(b"\r\n", b"\n"), 0o755))
    # DEBIAN control.tar uses members without DEBIAN/ prefix in modern debs? Actually control.tar has ./control
    ctrl_members = []
    ctrl_dirs: list[str] = []
    for n, b, m in control_files:
        ctrl_members.append((n, b, m))
    control_tar = tar_xz_from_files(ctrl_members, ctrl_dirs)
    data_tar = tar_xz_from_files(data_files, data_dirs)
    debian_binary = b"2.0\n"
    ar_write(
        out_path,
        [
            ("debian-binary", debian_binary),
            ("control.tar.xz", control_tar),
            ("data.tar.xz", data_tar),
        ],
    )
    return out_path.read_bytes()


def collect_payload() -> tuple[list[tuple[str, bytes, int]], list[str]]:
    files: list[tuple[str, bytes, int]] = []
    dirs: set[str] = set()
    base = PAYLOAD / "var"
    if not base.is_dir():
        raise SystemExit(f"Missing payload: {base}")
    for p in base.rglob("*"):
        rel = p.relative_to(PAYLOAD).as_posix()  # always forward slash
        if p.is_dir():
            dirs.add(rel)
            # parent dirs
            parts = rel.split("/")
            for i in range(1, len(parts)):
                dirs.add("/".join(parts[:i]))
        elif p.is_file():
            parts = rel.split("/")
            for i in range(1, len(parts)):
                dirs.add("/".join(parts[:i]))
            mode = 0o755 if p.suffix == ".dylib" or p.name == "Diso" or p.name == "postinst" else 0o644
            if p.name == "Diso" or p.suffix == ".dylib":
                mode = 0o755
            files.append((rel, p.read_bytes(), mode))
    return files, sorted(dirs)


def meta_control(name: str, version: str, desc: str, provides: str | None = None) -> str:
    lines = [
        f"Package: {name}",
        f"Version: {version}",
        f"Architecture: {ARCH}",
        f"Maintainer: Diso",
        f"Section: System",
        f"Priority: optional",
        f"Description: {desc}",
    ]
    if provides:
        lines.insert(5, f"Provides: {provides}")
    return "\n".join(lines) + "\n"


def write_packages_index(debs: list[tuple[Path, dict[str, str]]]) -> str:
    """debs: list of (path, extra control fields already including Package etc)."""
    blocks = []
    for path, ctrl in debs:
        data = path.read_bytes()
        md5, sha1, sha256 = sha_all(data)
        fields = dict(ctrl)
        fields["Filename"] = f"./debs/{path.name}"
        fields["Size"] = str(len(data))
        fields["MD5sum"] = md5
        fields["SHA1"] = sha1
        fields["SHA256"] = sha256
        order = [
            "Package",
            "Version",
            "Section",
            "Maintainer",
            "Architecture",
            "Depends",
            "Replaces",
            "Conflicts",
            "Provides",
            "Filename",
            "Size",
            "MD5sum",
            "SHA1",
            "SHA256",
            "Description",
            "Name",
            "Author",
            "Icon",
            "Priority",
        ]
        lines = []
        for k in order:
            if k in fields and fields[k]:
                lines.append(f"{k}: {fields[k]}")
        # any remaining
        for k, v in fields.items():
            if k not in order and v:
                lines.append(f"{k}: {v}")
        blocks.append("\n".join(lines) + "\n")
    return "\n".join(blocks) + "\n"


def write_apt_repo(packages_txt: str) -> None:
    if DOCS.exists():
        # keep icons if present
        icons = DOCS / "icons"
        icons_backup = None
        if icons.is_dir():
            icons_backup = ROOT / ".icons_bak"
            if icons_backup.exists():
                shutil.rmtree(icons_backup)
            shutil.copytree(icons, icons_backup)
        shutil.rmtree(DOCS)
    debs_dir = DOCS / "debs"
    debs_dir.mkdir(parents=True)
    # copy release debs
    for deb in sorted(RELEASE_DIR.glob("*.deb")):
        shutil.copy2(deb, debs_dir / deb.name)
    if (ROOT / ".icons_bak").is_dir():
        shutil.copytree(ROOT / ".icons_bak", DOCS / "icons")
        shutil.rmtree(ROOT / ".icons_bak")

    b = packages_txt.encode("utf-8")
    (DOCS / "Packages").write_bytes(b)
    (DOCS / "Packages.gz").write_bytes(gzip.compress(b, mtime=0))
    (DOCS / "Packages.bz2").write_bytes(bz2.compress(b))

    release = (
        "Origin: Diso\n"
        "Label: Diso\n"
        "Suite: stable\n"
        "Version: 1.0\n"
        "Codename: ios\n"
        f"Architectures: {ARCH}\n"
        "Components: main\n"
        "Description: Diso official APT repository\n"
    )
    (DOCS / "Release").write_bytes(release.encode("utf-8"))

    bdir = DOCS / "dists" / "stable" / "main" / f"binary-{ARCH}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "Packages").write_bytes(b)
    (bdir / "Packages.gz").write_bytes(gzip.compress(b, mtime=0))
    (bdir / "Packages.bz2").write_bytes(bz2.compress(b))
    (bdir / "Release").write_bytes(
        f"Archive: stable\nOrigin: Diso\nLabel: Diso\nComponent: main\nArchitecture: {ARCH}\n".encode()
    )
    (DOCS / "dists" / "stable" / "Release").write_bytes(release.encode("utf-8"))
    (DOCS / ".nojekyll").write_bytes(b"")

    index = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Diso APT</title>
<style>body{font-family:-apple-system,system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;line-height:1.5}
pre{background:#f4f4f5;padding:12px;border-radius:8px}.box{border:1px solid #e4e4e7;border-radius:12px;padding:14px;margin:12px 0}
a.btn{display:inline-block;background:#16a34a;color:#fff;padding:12px 16px;border-radius:10px;text-decoration:none;font-weight:600}</style>
</head><body>
<h1>Diso APT Repository</h1>
<div class="box"><b>Nguon Sileo:</b><pre>https://vpnhihi.github.io/diso/</pre></div>
<div class="box"><b>Package:</b> Diso 4.3.1 (rootless)<br/>
<a class="btn" href="debs/Diso_4.3.1_iphoneos-arm64.deb">Tai Diso.deb</a></div>
</body></html>
"""
    (DOCS / "index.html").write_bytes(index.encode("utf-8"))


def main() -> None:
    RELEASE_DIR.mkdir(exist_ok=True)

    # --- Diso main package only ---
    # Do NOT ship fake ellekit/mobilesubstrate: real ElleKit on Dopamine Conflicts
    # with a package named mobilesubstrate and Sileo tries to remove ElleKit/CCSupport.
    postinst = (PAYLOAD / "DEBIAN" / "postinst").read_text(encoding="utf-8")
    diso_control = f"""Package: com.diso.v3
Name: Diso
Version: 4.3.1
Architecture: {ARCH}
Maintainer: Diso
Author: Diso
Section: Tweaks
Depends: firmware (>= 15.0)
Replaces: com.changeinfoios.tweak, com.changeinfoios.app, com.changeinfoios, com.changeinfoios.bundle, com.changeinfoios.safari, com.changeinfoios.location, com.changeinfoios.zalo, com.changeinfoios.v3
Conflicts: com.changeinfoios.tweak, com.changeinfoios.bundle, com.changeinfoios.v3
Provides: com.changeinfoios.tweak
Description: Diso device spoof package for rootless jailbreak (Dopamine).
"""
    data_files, data_dirs = collect_payload()
    diso_deb = RELEASE_DIR / "Diso_4.3.1_iphoneos-arm64.deb"
    build_deb(diso_control, postinst, data_files, data_dirs, diso_deb)

    # Remove old meta debs that conflict with real ElleKit on device
    for old in RELEASE_DIR.glob("ellekit_*.deb"):
        old.unlink(missing_ok=True)
    for old in RELEASE_DIR.glob("mobilesubstrate_*.deb"):
        old.unlink(missing_ok=True)

    # verify no backslash paths
    import tarfile as tfmod

    deb_data = diso_deb.read_bytes()
    # quick ar parse for data.tar.xz
    assert deb_data.startswith(b"!<arch>\n")
    off = 8
    while off + 60 <= len(deb_data):
        h = deb_data[off : off + 60]
        name = h[0:16].decode().strip().rstrip("/")
        size = int(h[48:58].decode().strip())
        off += 60
        payload = deb_data[off : off + size]
        if name.startswith("data.tar"):
            raw = lzma.decompress(payload)
            with tfmod.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
                for m in tar.getmembers():
                    if "\\" in m.name:
                        raise SystemExit(f"backslash path still present: {m.name!r}")
            print("Diso data.tar paths: OK (forward slash only)")
        off += size
        if off % 2:
            off += 1

    # Packages index: Diso only (no fake ellekit/mobilesubstrate)
    debs_meta = [
        (
            diso_deb,
            {
                "Package": "com.diso.v3",
                "Version": "4.3.1",
                "Architecture": ARCH,
                "Maintainer": "Diso",
                "Section": "Tweaks",
                "Depends": "firmware (>= 15.0)",
                "Replaces": "com.changeinfoios.tweak, com.changeinfoios.app, com.changeinfoios, com.changeinfoios.bundle, com.changeinfoios.safari, com.changeinfoios.location, com.changeinfoios.zalo, com.changeinfoios.v3",
                "Conflicts": "com.changeinfoios.tweak, com.changeinfoios.bundle, com.changeinfoios.v3",
                "Provides": "com.changeinfoios.tweak",
                "Description": "Diso device spoof package for rootless jailbreak (Dopamine).",
                "Name": "Diso",
                "Author": "Diso",
                "Icon": "https://vpnhihi.github.io/diso/icons/diso.png",
            },
        ),
    ]

    packages_txt = write_packages_index(debs_meta)
    write_apt_repo(packages_txt)

    # also update payload DEBIAN/control to match
    (PAYLOAD / "DEBIAN" / "control").write_text(diso_control, encoding="utf-8", newline="\n")

    print("Built:")
    for p in sorted(RELEASE_DIR.glob("*.deb")):
        print(f"  {p.name} ({p.stat().st_size} bytes)")
    print("APT docs ready.")
    print(packages_txt)


if __name__ == "__main__":
    main()
