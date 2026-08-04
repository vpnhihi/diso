#!/usr/bin/env python3
"""Verify sheet-backed license API (HMAC + statuses)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:7474"
SECRET = b"hF9kQ2mZ7vX1pR4nL8wB6cT3yD5sG0aJeU2iO9rK4lM7nP1qV8xZ3bN6"


def check(key: str, udid: str, nonce: str = "n1") -> dict:
    data = urllib.parse.urlencode(
        {"key": key, "udid": udid, "nonce": nonce, "ts": str(int(time.time()))}
    ).encode()
    req = urllib.request.Request(
        BASE + "/check.php",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    ok_s = "1" if resp["ok"] else "0"
    msg = f"{ok_s}|{resp['status']}|{resp['expiry']}|{resp['daysLeft']}|{resp['ts']}|{resp['nonce']}"
    sig = hmac.new(SECRET, msg.encode(), hashlib.sha256).hexdigest()
    print(
        f"{key:12} status={resp['status']:12} ok={resp['ok']!s:5} "
        f"sig_ok={sig == resp['sig']!s:5} days={resp.get('daysLeft')}"
    )
    assert sig == resp["sig"], "HMAC mismatch"
    return resp


def main() -> None:
    health = json.loads(urllib.request.urlopen(BASE + "/health", timeout=10).read())
    print("health", health)
    assert health.get("ok") is True
    assert health.get("keys", 0) >= 1

    r = check("Admin", "IPF-4CE44B7C2A8A")
    assert r["ok"] is True and r["status"] == "ok"

    r = check("notexist_xyz", "ABC")
    assert r["ok"] is False and r["status"] == "not_found"

    r = check("Admin", "WRONGDEVICE999")
    assert r["ok"] is False and r["status"] == "wrong_device"

    print("ALL LICENSE TESTS PASSED")


if __name__ == "__main__":
    main()
