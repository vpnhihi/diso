# Diso

Package jailbreak rootless + kích key bằng **Google Sheet** + repo Sileo.

## Nguồn Sileo

```
https://vpnhihi.github.io/diso/
```

## Kích key (cách đơn giản — như trước)

**Sheet:**  
https://docs.google.com/spreadsheets/d/1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno

| Cột | Ý nghĩa |
|-----|---------|
| Key | Mã kích |
| Hạn sử dụng | Số ngày |
| ID MÁY | UDID (trống = bind máy đầu) |
| Tình trạng | **CHẠY** = dùng được |

Share sheet: **Anyone with the link → Viewer**.

### Trên PC (khi cần kích key)

```bash
cd license_server
python diso_license_server.py
```

Mặc định: `http://127.0.0.1:7474/check.php` (app đã trỏ sẵn).

**iPhone khác máy PC (cùng Wi‑Fi):**

1. Lấy IP LAN PC (vd `192.168.1.10`)
2. `python license_server/patch_license_url.py http://192.168.1.10:7474/`
3. Build lại deb / copy binary Diso

Không cần cloud / Apps Script / always-on.

## Build

```bash
python tools/simple_license_and_ui.py
python tools/build_debs_and_repo.py
```

## Yêu cầu

- iOS rootless JB ≥ 15  
- ellekit / mobilesubstrate  
