# LanGuard for macOS

Native macOS SwiftUI rewrite of LanGuard.

This app starts as a clean macOS 26+ codebase and does not reuse the existing Django or Next.js implementation.

## Current Scope

- SwiftUI app shell
- Dashboard screen
- Devices screen
- Scan history screen
- Settings screen
- Active local network discovery using ping, TCP probes, the macOS ARP table, and default route
- Local JSON persistence in Application Support
- Native macOS notifications when launched as a real app bundle
- App bundle packaging with resource support for a future bundled `manuf` vendor database

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
open .build/release/LanGuard-1.0.20.dmg
```

Drag `LanGuard.app` into `Applications` from the DMG window.
