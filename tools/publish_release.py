#!/usr/bin/env python3
"""Delete old GitHub releases, create v4.3.8 with deb asset."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEB = ROOT / "release" / "Diso_4.3.8_iphoneos-arm64.deb"
TAG = "v4.3.8"


def get_token() -> str:
    p = subprocess.run(
        [r"C:\Program Files\Git\mingw64\bin\git-credential-manager.exe", "get"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
    )
    for line in p.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no github token")


def api(token: str, method: str, url: str, body=None, content_type: str | None = None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "DisoRelease",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        if isinstance(body, (bytes, bytearray)):
            data = body
            headers["Content-Type"] = content_type or "application/octet-stream"
        else:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read()
            if not raw:
                return None
            try:
                return json.loads(raw.decode())
            except Exception:
                return raw
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:800])
        raise


def main() -> int:
    token = get_token()
    rels = api(token, "GET", "https://api.github.com/repos/vpnhihi/diso/releases")
    for r in rels or []:
        print("found", r["tag_name"], r["id"])
        if r["tag_name"] == TAG:
            print("deleting existing", TAG)
            api(token, "DELETE", f"https://api.github.com/repos/vpnhihi/diso/releases/{r['id']}")
            try:
                api(
                    token,
                    "DELETE",
                    f"https://api.github.com/repos/vpnhihi/diso/git/refs/tags/{TAG}",
                )
            except Exception as e:
                print("tag del", e)
            continue
        print("deleting old release", r["tag_name"])
        api(token, "DELETE", f"https://api.github.com/repos/vpnhihi/diso/releases/{r['id']}")
        try:
            api(
                token,
                "DELETE",
                f"https://api.github.com/repos/vpnhihi/diso/git/refs/tags/{r['tag_name']}",
            )
            print("deleted tag", r["tag_name"])
        except Exception as e:
            print("tag del", e)

    rel = api(
        token,
        "POST",
        "https://api.github.com/repos/vpnhihi/diso/releases",
        {
            "tag_name": TAG,
            "target_commitish": "main",
            "name": "Diso 4.3.8",
            "body": (
                "Full black UI + Google Sheet license (local server, simple).\n\n"
                "Sileo: https://vpnhihi.github.io/diso/\n\n"
                "Sheet: https://docs.google.com/spreadsheets/d/"
                "1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno\n\n"
                "On PC: `cd license_server && python diso_license_server.py`"
            ),
            "draft": False,
            "prerelease": False,
        },
    )
    print("created", rel.get("html_url"))
    upload = rel["upload_url"].split("{")[0]
    data = DEB.read_bytes()
    u = upload + "?name=" + urllib.parse.quote(DEB.name)
    asset = api(
        token,
        "POST",
        u,
        data,
        content_type="application/vnd.debian.binary-package",
    )
    print("asset", asset.get("browser_download_url"))
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
