# Diso

Jailbreak package (rootless) + license server (Google Sheet) + **Sileo APT repo**.

## Them nguon Sileo / Zebra

```
https://bgate6688-create.github.io/Diso/
```

1. Sileo → Sources → + → dan link tren  
2. Refresh → tim **Diso** → Install  
3. Respring / uicache neu can  

> Repo APT nam trong thu muc `docs/` (GitHub Pages).

## Cai dat .deb thu cong

- [`release/Diso_4.3.1_iphoneos-arm64.deb`](release/Diso_4.3.1_iphoneos-arm64.deb)
- Hoac: [`docs/debs/Diso_4.3.1_iphoneos-arm64.deb`](docs/debs/Diso_4.3.1_iphoneos-arm64.deb)

## License server (kich key Google Sheet)

```bash
cd license_server
python diso_license_server.py
```

- Endpoint: `http://PC_IP:7474/check.php`
- Binary mac dinh: `http://127.0.0.1:7474/`
- iPhone khac may PC:

```bash
python patch_license_url.py http://192.168.x.x:7474/
```

## Cau truc repo

```
docs/            # APT repo (Sileo source / GitHub Pages)
release/         # ban .deb goc
license_server/  # server kich key + patch URL
payload/         # DEBIAN + var/jb de dong goi lai
tools/           # build APT repo
```

## Yeu cau

- iOS rootless JB, firmware >= 15
- `ellekit` hoac `mobilesubstrate`
- Python 3 (license server tren PC)

## Build lai APT index (sau khi doi .deb)

```bash
python tools/build_apt_repo.py
```
