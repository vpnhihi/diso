# License server

## Chạy

```bash
python diso_license_server.py
```

- Endpoint: `POST /check.php`
- Health: `GET /health`
- Port: `7474` (đổi bằng `DISO_LIC_PORT`)

## Đổi URL trong app binary

```bash
python patch_license_url.py http://192.168.1.10:7474/
```

URL tối đa **22 ký tự**, phải kết thúc bằng `/` (app tự nối `check.php`).

Binary mặc định trong package:

`Diso.app/Diso` và `payload/var/jb/Applications/Diso.app/Diso`
