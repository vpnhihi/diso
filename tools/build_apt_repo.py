#!/usr/bin/env python3
"""Build a Sileo/Zebra-compatible APT repo into docs/ for GitHub Pages.

Provides BOTH layouts so clients work either way:
  - Flat:  /Packages, /Release, /debs/*.deb
  - Dist:  /dists/stable/main/binary-iphoneos-arm64/Packages
"""
from __future__ import annotations

import bz2
import gzip
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEB_SRC = ROOT / "release" / "Diso_4.3.1_iphoneos-arm64.deb"
DOCS = ROOT / "docs"
ARCH = "iphoneos-arm64"
SUITE = "stable"
COMPONENT = "main"


def file_hashes(path: Path):
    b = path.read_bytes()
    return (
        len(b),
        hashlib.md5(b).hexdigest(),
        hashlib.sha1(b).hexdigest(),
        hashlib.sha256(b).hexdigest(),
    )


def write_packages_set(directory: Path, packages_txt: str) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    names = []
    p = directory / "Packages"
    p.write_text(packages_txt, encoding="utf-8", newline="\n")
    names.append("Packages")
    gz = directory / "Packages.gz"
    gz.write_bytes(gzip.compress(packages_txt.encode("utf-8"), mtime=0))
    names.append("Packages.gz")
    bz = directory / "Packages.bz2"
    bz.write_bytes(bz2.compress(packages_txt.encode("utf-8")))
    names.append("Packages.bz2")
    return names


def make_release(
    *,
    suite: str | None,
    codename: str | None,
    components: str | None,
    architectures: str,
    date: str,
    hash_entries: list[tuple[str, Path]],
) -> str:
    """hash_entries: list of (path_in_release_file, filesystem_path)."""
    md5_lines, sha1_lines, sha256_lines = [], [], []
    for rel_name, path in hash_entries:
        sz, m, s1, s256 = file_hashes(path)
        md5_lines.append(f" {m} {sz} {rel_name}")
        sha1_lines.append(f" {s1} {sz} {rel_name}")
        sha256_lines.append(f" {s256} {sz} {rel_name}")

    lines = [
        "Origin: Diso",
        "Label: Diso",
        "Version: 1.0",
        f"Architectures: {architectures}",
        "Description: Diso official APT repository",
        f"Date: {date}",
    ]
    if suite:
        lines.insert(2, f"Suite: {suite}")
    if codename:
        lines.insert(3 if suite else 2, f"Codename: {codename}")
    if components:
        # keep near Architectures
        idx = next(i for i, l in enumerate(lines) if l.startswith("Architectures:"))
        lines.insert(idx + 1, f"Components: {components}")

    lines.extend(["MD5Sum:", *md5_lines, "SHA1:", *sha1_lines, "SHA256:", *sha256_lines, ""])
    return "\n".join(lines)


def main() -> None:
    if not DEB_SRC.is_file():
        raise SystemExit(f"Missing deb: {DEB_SRC}")

    if DOCS.exists():
        shutil.rmtree(DOCS)
    debs = DOCS / "debs"
    debs.mkdir(parents=True)

    deb_name = DEB_SRC.name
    deb_dst = debs / deb_name
    shutil.copy2(DEB_SRC, deb_dst)

    data = deb_dst.read_bytes()
    size = len(data)
    md5 = hashlib.md5(data).hexdigest()
    sha1 = hashlib.sha1(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()

    control = {
        "Package": "com.diso.v3",
        "Name": "Diso",
        "Version": "4.3.1",
        "Architecture": ARCH,
        "Maintainer": "Diso",
        "Author": "Diso",
        "Section": "Tweaks",
        "Depends": "ellekit | mobilesubstrate, firmware (>= 15.0)",
        "Replaces": (
            "com.changeinfoios.tweak, com.changeinfoios.app, com.changeinfoios, "
            "com.changeinfoios.bundle, com.changeinfoios.safari, "
            "com.changeinfoios.location, com.changeinfoios.zalo, com.changeinfoios.v3"
        ),
        "Conflicts": "com.changeinfoios.tweak, com.changeinfoios.bundle, com.changeinfoios.v3",
        "Provides": "com.changeinfoios.tweak",
        # Path from repository root (works for both flat and dist layouts)
        "Filename": f"debs/{deb_name}",
        "Size": str(size),
        "MD5sum": md5,
        "SHA1": sha1,
        "SHA256": sha256,
        "Description": (
            "Diso device spoof package (rootless). "
            "Requires license server for key activation."
        ),
    }

    order = [
        "Package",
        "Name",
        "Version",
        "Architecture",
        "Maintainer",
        "Author",
        "Section",
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
    ]
    packages_txt = "\n".join(f"{k}: {control[k]}" for k in order) + "\n\n"
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    # --- Flat layout (deb https://host/path/ ./) ---
    write_packages_set(DOCS, packages_txt)
    flat_release = make_release(
        suite=None,
        codename=None,
        components=None,
        architectures=ARCH,
        date=now,
        hash_entries=[
            ("Packages", DOCS / "Packages"),
            ("Packages.gz", DOCS / "Packages.gz"),
            ("Packages.bz2", DOCS / "Packages.bz2"),
        ],
    )
    (DOCS / "Release").write_text(flat_release, encoding="utf-8", newline="\n")

    # --- Dist layout (deb https://host/path/ stable main) ---
    binary_dir = DOCS / "dists" / SUITE / COMPONENT / f"binary-{ARCH}"
    write_packages_set(binary_dir, packages_txt)

    # per-arch Release (optional but helpful)
    arch_rel = "\n".join(
        [
            f"Archive: {SUITE}",
            f"Origin: Diso",
            f"Label: Diso",
            f"Component: {COMPONENT}",
            f"Architecture: {ARCH}",
            "",
        ]
    )
    (binary_dir / "Release").write_text(arch_rel, encoding="utf-8", newline="\n")

    dist_release = make_release(
        suite=SUITE,
        codename="diso",
        components=COMPONENT,
        architectures=ARCH,
        date=now,
        hash_entries=[
            (f"{COMPONENT}/binary-{ARCH}/Packages", binary_dir / "Packages"),
            (f"{COMPONENT}/binary-{ARCH}/Packages.gz", binary_dir / "Packages.gz"),
            (f"{COMPONENT}/binary-{ARCH}/Packages.bz2", binary_dir / "Packages.bz2"),
            (f"{COMPONENT}/binary-{ARCH}/Release", binary_dir / "Release"),
        ],
    )
    (DOCS / "dists" / SUITE / "Release").write_text(
        dist_release, encoding="utf-8", newline="\n"
    )

    index = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Diso APT Repo</title>
  <style>
    body { font-family: -apple-system, system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; line-height: 1.5; color: #18181b; }
    code, pre { background: #f4f4f5; padding: 2px 6px; border-radius: 6px; }
    pre { padding: 12px; overflow: auto; }
    .box { border: 1px solid #e4e4e7; border-radius: 12px; padding: 16px; margin: 16px 0; }
    a { color: #2563eb; }
  </style>
</head>
<body>
  <h1>Diso APT Repository</h1>
  <p>Nguon Sileo / Zebra (rootless, <code>iphoneos-arm64</code>).</p>
  <div class="box">
    <strong>Them nguon Sileo (dung dung link nay):</strong>
    <pre>https://vpnhihi.github.io/Diso/</pre>
  </div>
  <div class="box">
    <strong>Package:</strong> Diso 4.3.1 (<code>com.diso.v3</code>)<br/>
    <a href="debs/Diso_4.3.1_iphoneos-arm64.deb">Tai .deb truc tiep</a>
  </div>
  <p>Yeu cau: jailbreak <b>rootless</b> (Dopamine…), iOS &gt;= 15, ellekit/mobilesubstrate.</p>
</body>
</html>
"""
    (DOCS / "index.html").write_text(index, encoding="utf-8", newline="\n")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    print("Built APT repo in", DOCS)
    for p in sorted(DOCS.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(DOCS)}  ({p.stat().st_size})")


if __name__ == "__main__":
    main()
