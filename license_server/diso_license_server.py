#!/usr/bin/env python3
"""
Diso license server — drop-in replacement for flightmy.info/check.php
Reads license keys from the user's Google Sheet and returns signed JSON
compatible with the original HIOS/Diso client (HMAC-SHA256).

Sheet columns (row 1 header):
  STT | Key | Hạn sử dụng | ID MÁY | Tình trạng | GHI CHÚ

Protocol (same as original app):
  POST /check.php
  Content-Type: application/x-www-form-urlencoded
  body: key=...&udid=...&nonce=...&ts=...

  Response JSON:
    ok, status, expiry, daysLeft, ts, nonce, sig

  sig = hex(HMAC-SHA256(secret, "{0|1}|{status}|{expiry}|{daysLeft}|{ts}|{nonce}"))
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Original client HMAC secret (XOR-decoded from binary)
HMAC_SECRET = b"hF9kQ2mZ7vX1pR4nL8wB6cT3yD5sG0aJeU2iO9rK4lM7nP1qV8xZ3bN6"

SHEET_ID = "1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno"
SHEET_GID = "0"
SHEET_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"
)

HOST = os.environ.get("DISO_LIC_HOST", "0.0.0.0")
PORT = int(os.environ.get("DISO_LIC_PORT", "7474"))
BIND_DB = Path(__file__).resolve().parent / "device_bindings.json"
CACHE_TTL = 30  # seconds

_lock = threading.Lock()
_cache = {"ts": 0.0, "rows": []}


def _sign(ok: bool, status: str, expiry: str, days_left: int, ts: int, nonce: str) -> str:
    ok_s = "1" if ok else "0"
    msg = f"{ok_s}|{status}|{expiry}|{days_left}|{ts}|{nonce}"
    return hmac.new(HMAC_SECRET, msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _response(ok: bool, status: str, expiry: str, days_left: int, nonce: str, ts: int | None = None) -> dict:
    if ts is None:
        ts = int(time.time())
    expiry = expiry or ""
    days_left = int(days_left or 0)
    nonce = nonce or ""
    return {
        "ok": bool(ok),
        "status": status,
        "expiry": expiry,
        "daysLeft": days_left,
        "ts": ts,
        "nonce": nonce,
        "sig": _sign(bool(ok), status, expiry, days_left, ts, nonce),
    }


def _fetch_sheet_rows() -> list[dict]:
    now = time.time()
    with _lock:
        if now - _cache["ts"] < CACHE_TTL and _cache["rows"]:
            return list(_cache["rows"])

    req = urllib.request.Request(
        SHEET_CSV_URL,
        headers={"User-Agent": "DisoLicenseServer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read().decode("utf-8", errors="replace")

    # Prefer gviz-less simple CSV; handle quoted headers
    reader = csv.reader(io.StringIO(raw))
    rows_in = list(reader)
    if not rows_in:
        return []

    # Find header row (first non-empty)
    header = None
    data_start = 0
    for i, row in enumerate(rows_in):
        joined = ",".join(row).lower()
        if "key" in joined and ("hạn" in joined or "han" in joined or "id" in joined):
            header = [c.strip() for c in row]
            data_start = i + 1
            break
    if header is None:
        header = [c.strip() for c in rows_in[0]]
        data_start = 1

    # Normalize column indices by name
    def col(*names: str) -> int | None:
        low = [h.lower() for h in header]
        for n in names:
            for i, h in enumerate(low):
                if n in h:
                    return i
        return None

    i_key = col("key")
    i_days = col("hạn", "han", "days", "sử dụng", "su dung")
    i_dev = col("id máy", "id may", "máy", "may", "device", "udid")
    i_st = col("tình trạng", "tinh trang", "status", "trạng")
    i_note = col("ghi chú", "ghi chu", "note")

    out = []
    for row in rows_in[data_start:]:
        if not row or all(not (c or "").strip() for c in row):
            continue

        def get(idx):
            if idx is None or idx >= len(row):
                return ""
            return (row[idx] or "").strip()

        key = get(i_key)
        if not key:
            continue
        days_s = get(i_days)
        try:
            days = int(float(days_s)) if days_s else 0
        except ValueError:
            days = 0
        out.append(
            {
                "key": key,
                "days": days,
                "device": get(i_dev),
                "status": get(i_st),
                "note": get(i_note),
            }
        )

    with _lock:
        _cache["ts"] = now
        _cache["rows"] = out
    return list(out)


def _load_binds() -> dict:
    if not BIND_DB.exists():
        return {}
    try:
        return json.loads(BIND_DB.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_binds(binds: dict) -> None:
    BIND_DB.write_text(json.dumps(binds, ensure_ascii=False, indent=2), encoding="utf-8")


def _status_active(st: str) -> bool:
    s = (st or "").strip().upper()
    if not s:
        return False
    # CHẠY / CHAY / ACTIVE / OK / RUN
    s_ascii = (
        s.replace("Ạ", "A")
        .replace("Ă", "A")
        .replace("Â", "A")
        .replace("Ê", "E")
        .replace("Ô", "O")
        .replace("Ơ", "O")
        .replace("Ư", "U")
    )
    return s in ("CHẠY", "CHAY", "ACTIVE", "OK", "RUN", "1", "TRUE", "YES") or "CHAY" in s_ascii


def _devices_match(sheet_dev: str, udid: str) -> bool:
    if not sheet_dev:
        return True
    a = sheet_dev.strip().upper()
    b = (udid or "").strip().upper()
    if a == b:
        return True
    # allow suffix match (IPF-XXX vs raw)
    if a.endswith(b) or b.endswith(a):
        return True
    # strip common prefixes
    for p in ("IPF-", "HIOSV3|", "HIOS-", "DISO-"):
        if a.startswith(p):
            a2 = a[len(p) :]
            if a2 == b or b.endswith(a2):
                return True
        if b.startswith(p):
            b2 = b[len(p) :]
            if a == b2 or a.endswith(b2):
                return True
    return False


def validate_key(key: str, udid: str, nonce: str, req_ts: int | None) -> dict:
    ts = int(time.time())
    key = (key or "").strip()
    udid = (udid or "").strip()
    nonce = (nonce or "").strip() or "0"

    if not key:
        return _response(False, "need_key", "", 0, nonce, ts)

    try:
        rows = _fetch_sheet_rows()
    except Exception as e:
        return _response(False, "not_found", "", 0, nonce, ts)

    row = next((r for r in rows if r["key"] == key), None)
    if row is None:
        # case-insensitive fallback
        row = next((r for r in rows if r["key"].lower() == key.lower()), None)
    if row is None:
        return _response(False, "not_found", "", 0, nonce, ts)

    if not _status_active(row["status"]):
        return _response(False, "revoked", "", 0, nonce, ts)

    days = int(row["days"] or 0)
    if days <= 0:
        return _response(False, "expired", "", 0, nonce, ts)

    sheet_dev = row["device"]
    binds = _load_binds()
    bound = (sheet_dev or binds.get(key) or "").strip()

    if bound:
        if not _devices_match(bound, udid):
            return _response(False, "wrong_device", "", 0, nonce, ts)
    else:
        # first activation: bind udid server-side (sheet is read-only without OAuth)
        if udid:
            binds[key] = udid
            binds[f"{key}__bound_at"] = datetime.now(timezone.utc).isoformat()
            _save_binds(binds)
            bound = udid

    expiry_dt = datetime.now(timezone.utc) + timedelta(days=days)
    expiry = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return _response(True, "ok", expiry, days, nonce, ts)


class Handler(BaseHTTPRequestHandler):
    server_version = "DisoLicense/1.0"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: dict):
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/health"):
            try:
                rows = _fetch_sheet_rows()
                self._send(
                    200,
                    {
                        "ok": True,
                        "service": "DisoLicense",
                        "keys": len(rows),
                        "sheet": SHEET_ID,
                    },
                )
            except Exception as e:
                self._send(500, {"ok": False, "error": str(e)})
            return
        if path.endswith("check.php") or path == "/check":
            # allow GET for quick debug
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            key = (qs.get("key") or [""])[0]
            udid = (qs.get("udid") or [""])[0]
            nonce = (qs.get("nonce") or ["dbg"])[0]
            self._send(200, validate_key(key, udid, nonce, None))
            return
        self._send(404, {"ok": False, "status": "not_found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not (path.endswith("check.php") or path in ("/check", "/check.php")):
            self._send(404, {"ok": False, "status": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        ctype = (self.headers.get("Content-Type") or "").lower()
        key = udid = nonce = ""
        req_ts = None
        if "application/json" in ctype:
            try:
                obj = json.loads(raw.decode("utf-8") or "{}")
                key = str(obj.get("key") or "")
                udid = str(obj.get("udid") or "")
                nonce = str(obj.get("nonce") or "")
                req_ts = obj.get("ts")
            except Exception:
                pass
        else:
            form = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
            key = (form.get("key") or [""])[0]
            udid = (form.get("udid") or [""])[0]
            nonce = (form.get("nonce") or [""])[0]
            if form.get("ts"):
                try:
                    req_ts = int(form["ts"][0])
                except ValueError:
                    req_ts = None
        self._send(200, validate_key(key, udid, nonce, req_ts))


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Diso license server on http://{HOST}:{PORT}")
    print(f"  check endpoint: POST http://127.0.0.1:{PORT}/check.php")
    print(f"  sheet: {SHEET_CSV_URL}")
    print(f"  binds: {BIND_DB}")
    try:
        rows = _fetch_sheet_rows()
        print(f"  loaded {len(rows)} keys: {[r['key'] for r in rows]}")
    except Exception as e:
        print(f"  WARNING sheet fetch failed: {e}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
