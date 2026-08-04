/**
 * Diso public license — Cloudflare Worker (no redirect, works on iOS).
 * Reads Google Sheet CSV live. Deploy: npx wrangler deploy
 */
const HMAC_SECRET = "hF9kQ2mZ7vX1pR4nL8wB6cT3yD5sG0aJeU2iO9rK4lM7nP1qV8xZ3bN6";
const SHEET_ID = "1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno";
const SHEET_GID = "0";
const CACHE_TTL_MS = 30_000;
let cache = { ts: 0, rows: [] };
const binds = new Map();

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }
    const path = url.pathname;
    if (path === "/health" || path === "/") {
      try {
        const rows = await fetchSheetRows();
        return json({ ok: true, service: "DisoLicense", keys: rows.length });
      } catch (e) {
        return json({ ok: false, error: String(e) }, 500);
      }
    }
    if (!(path.endsWith("check.php") || path === "/check" || path.endsWith("/check"))) {
      // also accept bare / for license POST (some clients)
      if (request.method === "POST" || url.searchParams.has("key")) {
        /* fall through to check */
      } else {
        return json({ ok: false, status: "not_found" }, 404);
      }
    }
    let key = "",
      udid = "",
      nonce = "0";
    if (request.method === "GET") {
      key = url.searchParams.get("key") || "";
      udid = url.searchParams.get("udid") || "";
      nonce = url.searchParams.get("nonce") || "0";
    } else {
      const raw = await request.text();
      const ctype = (request.headers.get("content-type") || "").toLowerCase();
      if (ctype.includes("application/json")) {
        try {
          const obj = JSON.parse(raw || "{}");
          key = String(obj.key || "");
          udid = String(obj.udid || "");
          nonce = String(obj.nonce || "0");
        } catch (_) {}
      } else {
        const form = new URLSearchParams(raw);
        key = form.get("key") || "";
        udid = form.get("udid") || "";
        nonce = form.get("nonce") || "0";
      }
    }
    return json(await validateKey(key, udid, nonce));
  },
};

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

function sign(ok, status, expiry, daysLeft, ts, nonce) {
  const okS = ok ? "1" : "0";
  const msg = `${okS}|${status}|${expiry}|${daysLeft}|${ts}|${nonce}`;
  // Web Crypto
  return crypto.subtle
    .importKey(
      "raw",
      new TextEncoder().encode(HMAC_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    )
    .then((key) =>
      crypto.subtle.sign("HMAC", key, new TextEncoder().encode(msg))
    )
    .then((sig) =>
      [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("")
    );
}

async function response(ok, status, expiry, daysLeft, nonce, ts) {
  ts = ts || Math.floor(Date.now() / 1000);
  expiry = expiry || "";
  daysLeft = daysLeft | 0;
  nonce = nonce || "";
  return {
    ok: !!ok,
    status,
    expiry,
    daysLeft,
    ts,
    nonce,
    sig: await sign(!!ok, status, expiry, daysLeft, ts, nonce),
  };
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          cur += '"';
          i++;
        } else inQ = false;
      } else cur += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") {
      row.push(cur);
      cur = "";
    } else if (c === "\n") {
      row.push(cur);
      rows.push(row);
      row = [];
      cur = "";
    } else if (c !== "\r") cur += c;
  }
  if (cur.length || row.length) {
    row.push(cur);
    rows.push(row);
  }
  return rows;
}

async function fetchSheetRows() {
  const now = Date.now();
  if (now - cache.ts < CACHE_TTL_MS && cache.rows.length) return cache.rows.slice();
  const csvUrl = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/export?format=csv&gid=${SHEET_GID}`;
  const r = await fetch(csvUrl, { headers: { "User-Agent": "DisoLicenseWorker/1.0" } });
  if (!r.ok) throw new Error("sheet http " + r.status);
  const text = await r.text();
  const rowsIn = parseCsv(text);
  if (!rowsIn.length) return [];
  let header = null;
  let dataStart = 0;
  for (let i = 0; i < rowsIn.length; i++) {
    const joined = rowsIn[i].join(",").toLowerCase();
    if (
      joined.includes("key") &&
      (joined.includes("hạn") ||
        joined.includes("han") ||
        joined.includes("id") ||
        joined.includes("tình") ||
        joined.includes("tinh"))
    ) {
      header = rowsIn[i].map((c) => String(c || "").trim());
      dataStart = i + 1;
      break;
    }
  }
  if (!header) {
    header = rowsIn[0].map((c) => String(c || "").trim());
    dataStart = 1;
  }
  const col = (...names) => {
    const low = header.map((h) => h.toLowerCase());
    for (const n of names) {
      for (let i = 0; i < low.length; i++) if (low[i].includes(n)) return i;
    }
    return -1;
  };
  const iKey = col("key");
  const iDays = col("hạn", "han", "days", "sử dụng", "su dung");
  const iDev = col("id máy", "id may", "máy", "may", "device", "udid");
  const iSt = col("tình trạng", "tinh trang", "status", "trạng");
  const out = [];
  for (let r = dataStart; r < rowsIn.length; r++) {
    const row = rowsIn[r];
    if (!row || !row.length) continue;
    const get = (idx) =>
      idx < 0 || idx >= row.length ? "" : String(row[idx] || "").trim();
    const key = get(iKey);
    if (!key) continue;
    let days = parseInt(get(iDays), 10);
    if (Number.isNaN(days)) days = 0;
    out.push({ key, days, device: get(iDev), status: get(iSt) });
  }
  cache = { ts: now, rows: out };
  return out.slice();
}

function statusActive(st) {
  let s = String(st || "")
    .trim()
    .toUpperCase();
  if (!s) return false;
  const ascii = s
    .replace(/Ạ/g, "A")
    .replace(/Ă/g, "A")
    .replace(/Â/g, "A")
    .replace(/Ê/g, "E")
    .replace(/Ô/g, "O")
    .replace(/Ơ/g, "O")
    .replace(/Ư/g, "U");
  return (
    ["CHẠY", "CHAY", "ACTIVE", "OK", "RUN", "1", "TRUE", "YES"].includes(s) ||
    ascii.includes("CHAY")
  );
}

function devicesMatch(sheetDev, udid) {
  if (!sheetDev) return true;
  let a = String(sheetDev).trim().toUpperCase();
  let b = String(udid || "")
    .trim()
    .toUpperCase();
  if (a === b) return true;
  if (a.endsWith(b) || b.endsWith(a)) return true;
  for (const p of ["IPF-", "HIOSV3|", "HIOS-", "DISO-"]) {
    if (a.startsWith(p)) {
      const a2 = a.slice(p.length);
      if (a2 === b || b.endsWith(a2)) return true;
    }
    if (b.startsWith(p)) {
      const b2 = b.slice(p.length);
      if (a === b2 || a.endsWith(b2)) return true;
    }
  }
  return false;
}

async function validateKey(key, udid, nonce) {
  const ts = Math.floor(Date.now() / 1000);
  key = String(key || "").trim();
  udid = String(udid || "").trim();
  nonce = String(nonce || "").trim() || "0";
  if (!key) return response(false, "need_key", "", 0, nonce, ts);
  let rows;
  try {
    rows = await fetchSheetRows();
  } catch (_) {
    return response(false, "not_found", "", 0, nonce, ts);
  }
  let row =
    rows.find((r) => r.key === key) ||
    rows.find((r) => r.key.toLowerCase() === key.toLowerCase());
  if (!row) return response(false, "not_found", "", 0, nonce, ts);
  if (!statusActive(row.status)) return response(false, "revoked", "", 0, nonce, ts);
  const days = row.days | 0;
  if (days <= 0) return response(false, "expired", "", 0, nonce, ts);
  const sheetDev = (row.device || "").trim();
  let bound = sheetDev || binds.get(key) || "";
  if (bound) {
    if (!devicesMatch(bound, udid))
      return response(false, "wrong_device", "", 0, nonce, ts);
  } else if (udid) {
    binds.set(key, udid);
  }
  const expiry = new Date(Date.now() + days * 86400000)
    .toISOString()
    .replace(/\.\d{3}Z$/, "Z");
  return response(true, "ok", expiry, days, nonce, ts);
}
