# Diso

Package jailbreak rootless + kích key **Google Sheet** + repo Sileo.

## Nguồn Sileo

```
https://vpnhihi.github.io/diso/
```

## Kích key (khách — không cần cùng Wi‑Fi / không cần bật PC)

App gọi **server public** (Google Apps Script) đọc key đã sync từ Sheet.

**Sheet shop:**  
https://docs.google.com/spreadsheets/d/1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno

| Cột | Ý nghĩa |
|-----|---------|
| Key | Mã kích |
| Hạn sử dụng | Số ngày |
| ID MÁY | UDID (trống = bind máy đầu) |
| Tình trạng | **CHẠY** = dùng được |

Share: **Anyone with the link → Viewer**.

### Khi thêm / sửa key trên Sheet

Chạy 1 lệnh trên PC (đồng bộ key lên server public):

```bat
cd /d C:\Users\ADMIN\Desktop\Diso-Release\Diso-Release
python tools\sync_sheet_public_license.py
```

Sau đó **không cần** bật server khi khách kích.  
(Có thể đặt Task Scheduler chạy lệnh trên mỗi 10–30 phút nếu hay thêm key.)

### Local test (tuỳ chọn)

```bat
cd license_server
python diso_license_server.py
```

## Build

```bat
python tools\sync_sheet_public_license.py
python tools\set_public_license_url.py
python tools\build_debs_and_repo.py
```

## Yêu cầu máy khách

- iOS rootless JB ≥ 15  
- Internet (4G/Wi‑Fi bất kỳ)  
- ellekit / mobilesubstrate  
