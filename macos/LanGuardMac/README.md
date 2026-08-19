# LanGuard for macOS

Native macOS SwiftUI rewrite of LanGuard.

This app starts as a clean native SwiftUI codebase and does not reuse the Django or Next.js implementation.

## Current Scope

- SwiftUI app shell
- Dashboard screen
- Devices screen
- Grouping screen for rooms and roles
- Guest scan screen
- Scan history screen
- Settings screen
- Active local network discovery using ping, TCP probes, hostname probes, the macOS ARP table, and default route
- Vendor lookup using the bundled Wireshark `manuf` database
- Role-aware risk scoring for known cameras, intercoms, and servers with expected open ports
- Latest Scan details sheet with scan duration, started/finished times, status, and deep scan checks
- Device inventory export/import for moving names, icons, rooms, roles, vendors, IPs, MAC addresses, and open ports between installs
- Import/export success and failure feedback in Settings
- Automatic scanning that waits for the configured interval after each scan completes
- Local JSON persistence in Application Support
- Native macOS notifications when launched as a real app bundle
- App bundle packaging with bundled resources

Automatic scanning schedules the next scan after the current scan completes. For example, with a 5 minute interval, a scan that finishes at 20:14 will schedule the next scan for about 20:19.

## Demo Screenshots

Use [`../../docs/demo-inventory.json`](../../docs/demo-inventory.json) when preparing public screenshots. Import it from Settings before taking screenshots so images never expose real device names, IP addresses, MAC addresses, rooms, or hostnames.

## Run During Development

```bash
swift run
```

## Build The App Bundle

```bash
./Scripts/build_app.sh
open .build/app/LanGuard.app
```

The app bundle is created at `.build/app/LanGuard.app`.

## Build The Installer DMG

```bash
./Scripts/build_dmg.sh
open .build/release/LanGuard-1.1.6.dmg
```

Drag `LanGuard.app` into `Applications` from the DMG window.
