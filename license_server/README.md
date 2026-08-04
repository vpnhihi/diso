# License server (đơn giản)

Đọc key từ Google Sheet, trả JSON HMAC cho app.

## Sheet

https://docs.google.com/spreadsheets/d/1cnfHaeZc1SfDCQZGWI4CDV3vXIT6kGxgCCbVwhPGyno

## Chạy

```bash
python diso_license_server.py
```

- Endpoint: `POST http://127.0.0.1:7474/check.php`
- App mặc định trỏ `http://127.0.0.1:7474/` + `check.php`

## iPhone khác PC

```bash
python patch_license_url.py http://192.168.x.x:7474/
```

(URL tối đa 22 ký tự, kết thúc bằng `/`)
