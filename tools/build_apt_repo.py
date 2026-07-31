#!/usr/bin/env python3
"""Build a simple Cydia/Sileo-compatible APT repo into docs/ for GitHub Pages."""
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
        "Architecture": "iphoneos-arm64",
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
        "Description": (
            "Diso device spoof package (rootless). "
            "Requires license server for key activation."
        ),
        "Filename": f"debs/{deb_name}",
        "Size": str(size),
        "MD5sum": md5,
        "SHA1": sha1,
        "SHA256": sha256,
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
    (DOCS / "Packages").write_text(packages_txt, encoding="utf-8", newline="\n")
    (DOCS / "Packages.gz").write_bytes(
        gzip.compress(packages_txt.encode("utf-8"), mtime=0)
    )
    (DOCS / "Packages.bz2").write_bytes(bz2.compress(packages_txt.encode("utf-8")))

    def file_hashes(path: Path):
        b = path.read_bytes()
        return (
            len(b),
            hashlib.md5(b).hexdigest(),
            hashlib.sha1(b).hexdigest(),
            hashlib.sha256(b).hexdigest(),
        )

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    files = ["Packages", "Packages.gz", "Packages.bz2"]
    md5_lines = []
    sha1_lines = []
    sha256_lines = []
    for f in files:
        sz, m, s1, s256 = file_hashes(DOCS / f)
        md5_lines.append(f" {m} {sz} {f}")
        sha1_lines.append(f" {s1} {sz} {f}")
        sha256_lines.append(f" {s256} {sz} {f}")

    release = "\n".join(
        [
            "Origin: Diso",
            "Label: Diso",
            "Suite: stable",
            "Version: 1.0",
            "Codename: diso",
            "Architectures: iphoneos-arm64",
            "Components: main",
            "Description: Diso official APT repository",
            f"Date: {now}",
            "MD5Sum:",
            *md5_lines,
            "SHA1:",
            *sha1_lines,
            "SHA256:",
            *sha256_lines,
            "",
        ]
    )
    (DOCS / "Release").write_text(release, encoding="utf-8", newline="\n")

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
  <p>Nguồn Sileo / Zebra (rootless, <code>iphoneos-arm64</code>).</p>
  <div class="box">
    <strong>Them nguon Sileo:</strong>
    <pre>https://vpnhihi.github.io/Diso/</pre>
  </div>
  <div class="box">
    <strong>Package:</strong> Diso 4.3.1 (<code>com.diso.v3</code>)<br/>
    <a href="debs/Diso_4.3.1_iphoneos-arm64.deb">Tai .deb truc tiep</a>
  </div>
  <p>Sau khi cai: bat license server tren PC de kich key (xem README tren GitHub).</p>
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
