#!/usr/bin/env python3
"""Build a Sileo/Zebra-compatible APT repo into docs/ for GitHub Pages.

Matches field layout used by known-working Sileo repos (Chariz / dylbin style):
  Origin, Label, Suite, Version, Codename, Architectures, Components, Description,
  optional Date + checksums.
Also writes dists/stable/... for clients that expect a dist layout.
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
CODENAME = "ios"


def file_hashes(path: Path):
    b = path.read_bytes()
    return (
        len(b),
        hashlib.md5(b).hexdigest(),
        hashlib.sha1(b).hexdigest(),
        hashlib.sha256(b).hexdigest(),
    )


def write_packages_set(directory: Path, packages_txt: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Packages").write_bytes(packages_txt.encode("utf-8"))
    (directory / "Packages.gz").write_bytes(
        gzip.compress(packages_txt.encode("utf-8"), mtime=0)
    )
    (directory / "Packages.bz2").write_bytes(
        bz2.compress(packages_txt.encode("utf-8"))
    )


def make_release(
    *,
    date: str,
    hash_entries: list[tuple[str, Path]],
    include_suite: bool = True,
) -> bytes:
    """Build a Release file as LF-only UTF-8 bytes (no BOM)."""
    lines = [
        "Origin: Diso",
        "Label: Diso",
    ]
    if include_suite:
        lines.extend(
            [
                f"Suite: {SUITE}",
                "Version: 1.0",
                f"Codename: {CODENAME}",
                f"Architectures: {ARCH}",
                f"Components: {COMPONENT}",
            ]
        )
    else:
        lines.extend(
            [
                "Version: 1.0",
                f"Architectures: {ARCH}",
            ]
        )
    lines.extend(
        [
            "Description: Diso official APT repository",
            f"Date: {date}",
        ]
    )

    md5_lines, sha1_lines, sha256_lines = [], [], []
    for rel_name, path in hash_entries:
        sz, m, s1, s256 = file_hashes(path)
        # Debian format: leading space + hash + space + size + space + filename
        md5_lines.append(f" {m} {sz} {rel_name}")
        sha1_lines.append(f" {s1} {sz} {rel_name}")
        sha256_lines.append(f" {s256} {sz} {rel_name}")

    lines.append("MD5Sum:")
    lines.extend(md5_lines)
    lines.append("SHA1:")
    lines.extend(sha1_lines)
    lines.append("SHA256:")
    lines.extend(sha256_lines)
    # trailing blank line
    text = "\n".join(lines) + "\n"
    return text.encode("utf-8")


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

    # Field order mirrors typical Cydia/Sileo package stanzas
    fields = [
        ("Package", "com.diso.v3"),
        ("Name", "Diso"),
        ("Version", "4.3.1"),
        ("Architecture", ARCH),
        ("Maintainer", "Diso"),
        ("Author", "Diso"),
        ("Section", "Tweaks"),
        ("Depends", "ellekit | mobilesubstrate, firmware (>= 15.0)"),
        (
            "Replaces",
            "com.changeinfoios.tweak, com.changeinfoios.app, com.changeinfoios, "
            "com.changeinfoios.bundle, com.changeinfoios.safari, "
            "com.changeinfoios.location, com.changeinfoios.zalo, com.changeinfoios.v3",
        ),
        (
            "Conflicts",
            "com.changeinfoios.tweak, com.changeinfoios.bundle, com.changeinfoios.v3",
        ),
        ("Provides", "com.changeinfoios.tweak"),
        ("Filename", f"./debs/{deb_name}"),
        ("Size", str(size)),
        ("MD5sum", md5),
        ("SHA1", sha1),
        ("SHA256", sha256),
        (
            "Description",
            "Diso device spoof package (rootless). Requires license server for key activation.",
        ),
    ]
    packages_txt = "\n".join(f"{k}: {v}" for k, v in fields) + "\n\n"
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Flat layout at docs root
    write_packages_set(DOCS, packages_txt)
    flat_release = make_release(
        date=now,
        hash_entries=[
            ("Packages", DOCS / "Packages"),
            ("Packages.gz", DOCS / "Packages.gz"),
            ("Packages.bz2", DOCS / "Packages.bz2"),
        ],
        include_suite=True,
    )
    (DOCS / "Release").write_bytes(flat_release)

    # Dist layout
    binary_dir = DOCS / "dists" / SUITE / COMPONENT / f"binary-{ARCH}"
    write_packages_set(binary_dir, packages_txt)
    (binary_dir / "Release").write_bytes(
        (
            f"Archive: {SUITE}\n"
            f"Origin: Diso\n"
            f"Label: Diso\n"
            f"Component: {COMPONENT}\n"
            f"Architecture: {ARCH}\n"
        ).encode("utf-8")
    )
    dist_release = make_release(
        date=now,
        hash_entries=[
            (f"{COMPONENT}/binary-{ARCH}/Packages", binary_dir / "Packages"),
            (f"{COMPONENT}/binary-{ARCH}/Packages.gz", binary_dir / "Packages.gz"),
            (f"{COMPONENT}/binary-{ARCH}/Packages.bz2", binary_dir / "Packages.bz2"),
            (f"{COMPONENT}/binary-{ARCH}/Release", binary_dir / "Release"),
        ],
        include_suite=True,
    )
    (DOCS / "dists" / SUITE / "Release").write_bytes(dist_release)

    # Minimal InRelease is NOT signed — don't create a fake one.
    # Some clients prefer unsigned Release only.

    index = """<!DOCTYPE html>
<html lang=\"vi\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
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
  <div class=\"box\">
    <strong>Them nguon Sileo (chu thuong):</strong>
    <pre>https://vpnhihi.github.io/diso/</pre>
  </div>
  <div class=\"box\">
    <strong>Mirror (neu GitHub Pages loi):</strong>
    <pre>https://cdn.jsdelivr.net/gh/vpnhihi/diso@main/docs/</pre>
  </div>
  <div class=\"box\">
    <strong>Package:</strong> Diso 4.3.1 (<code>com.diso.v3</code>)<br/>
    <a href=\"debs/Diso_4.3.1_iphoneos-arm64.deb\">Tai .deb truc tiep</a>
  </div>
</body>
</html>
"""
    (DOCS / "index.html").write_bytes(index.encode("utf-8"))
    (DOCS / ".nojekyll").write_bytes(b"")

    # Prevent GitHub Pages from treating empty dirs oddly
    print("Built APT repo in", DOCS)
    for p in sorted(DOCS.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(DOCS)}  ({p.stat().st_size})")


if __name__ == "__main__":
    main()
