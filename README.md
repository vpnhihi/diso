# Diso

Jailbreak package (rootless) + license server (Google Sheet).

## Cài đặt nhanh (iPhone)

1. Cài file:
   - [`release/Diso_4.3.1_iphoneos-arm64.deb`](release/Diso_4.3.1_iphoneos-arm64.deb)
   - Filza / Sileo / `dpkg -i`
2. Respring hoặc `uicache` nếu icon chưa hiện.
3. Bật **license server** trên PC (bắt buộc để kích key):

```bash
cd license_server
python diso_license_server.py
```

Server mặc định: `http://0.0.0.0:7474/check.php`

4. **iPhone và PC khác máy** — đổi URL license sang IP LAN PC (≤ 22 ký tự, có `/` cuối):

```bash
python patch_license_url.py http://192.168.x.x:7474/
```

Sau đó copy binary đã patch vào:

`/var/jb/Applications/Diso.app/Diso`

hoặc build lại `.deb` từ `payload/`.

5. Mở app **Diso** → nhập key trong Google Sheet (trạng thái `CHẠY`).

## Cấu trúc repo (chỉ file cần dùng)

```
release/                  # .deb cài trực tiếp
license_server/           # server kích key + tool patch URL
payload/                  # source package (DEBIAN + var/jb) để đóng gói lại
```

## License key (Google Sheet)

App đọc key qua license server → Google Sheet:

| Cột | Ý nghĩa |
|-----|---------|
| Key | Mã kích |
| Hạn sử dụng | Số ngày |
| ID MÁY | UDID / IPF-… (trống = bind máy đầu) |
| Tình trạng | `CHẠY` = active |

## Đóng gói lại .deb (tùy chọn)

Trên Linux/macOS/WSL:

```bash
cd payload
tar -cJf data.tar.xz var
tar -cJf control.tar.xz -C DEBIAN .
echo 2.0 > debian-binary
ar r ../release/Diso_4.3.1_iphoneos-arm64.deb debian-binary control.tar.xz data.tar.xz
```

## Yêu cầu

- iOS rootless jailbreak (Dopamine / …), firmware ≥ 15
- `ellekit` hoặc `mobilesubstrate`
- Python 3 (cho license server trên PC)

## Lưu ý

- Binary mặc định trỏ `http://127.0.0.1:7474/` — chỉ đúng nếu server chạy trên chính thiết bị.
- Dylib spoof giữ nguyên protocol gốc; không cần cấu hình thêm ngoài license server.
