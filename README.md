# Diso

Jailbreak package (rootless) + license server + **Sileo APT repo**.

## Nguon Sileo / Zebra

```
https://vpnhihi.github.io/diso/
```

### Cach them
1. Sileo → **Sources** → **+**
2. Dan: `https://vpnhihi.github.io/diso/`
3. Refresh → tim **Diso** → Install

### File APT (trong `docs/`)
- `Release`, `Packages`, `Packages.gz`, `Packages.bz2`
- `debs/Diso_4.3.1_iphoneos-arm64.deb`

## Tai .deb truc tiep

- Release: https://github.com/vpnhihi/diso/releases/tag/v4.3.1
- Repo: `release/Diso_4.3.1_iphoneos-arm64.deb`

## License server (kich key Google Sheet)

```bash
cd license_server
python diso_license_server.py
```

iPhone khac PC:

```bash
python patch_license_url.py http://192.168.x.x:7474/
```

## Build lai APT index

```bash
python tools/build_apt_repo.py
git add docs && git commit -m "update apt" && git push
```

## Luu y quan trong ve GitHub account

Neu may khac **khong** thay repo / Sileo **khong** refresh duoc:
- Tai khoan GitHub can **public + verify email**
- Vao https://github.com/settings/emails xac minh email
- Vao https://github.com/settings/profile dam bao profile/repo public
- Thu mo an danh: https://github.com/vpnhihi/diso (phai ra 200, khong 404)

## Yeu cau may

- iOS rootless JB, firmware >= 15
- ellekit | mobilesubstrate
