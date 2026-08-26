# Changelog

## 1.6.0 - 2026-08-26

- Added per-channel test actions for configured Discord and Telegram notifications.
- Added `First Seen` filtering and sorting to the Docker and macOS device lists.
- Improved Docker server-unavailable messages without exposing internal API or server details.
- Fixed unnecessary page-level horizontal scrolling in the Docker interface.
- Fixed clipped port-overflow indicators and improved device-list port spacing.

## 1.5.0 - 2026-08-25

- Added access to device details directly from rows on the Events page.
- Fixed acknowledged device risks returning to Needs Attention after routine scan metadata updates.
- **Breaking change:** Docker deployments must change the scanner service image from `ghcr.io/hillaliy/languard-backend` to `ghcr.io/hillaliy/languard-scheduler`.
- Added a separate scheduled-scanner Docker image to prevent container updaters from confusing it with the backend service.
- Improved Docker hostname discovery with one-shot mDNS queries and scan-wide metadata batching.
- Improved Docker and macOS hostname discovery with dynamic DNS-SD service browsing and cross-packet record correlation.
- Added optional external device links in Docker and macOS with verified local web-interface suggestions.
- Sorted Docker role choices alphabetically by their displayed labels.

## 1.4.0 - 2026-08-25

- Added device comments in Docker and macOS.
- Added an option for known devices to acknowledge the current risk and remove them from Needs Attention.
- Automatically invalidated risk acknowledgements when ports or other risk-related device details change.
- Added comments and risk acknowledgement compatibility to inventory export and import between Docker and macOS.

## 1.3.2 - 2026-08-24

- Added direct device editing from the Recently Changed list in Docker and macOS.
- Improved Events, Scan history, and Notifications scrolling beyond 500 records.
- Clarified cleanup actions and fixed Home Map room backgrounds in dark mode.
- Updated Granian to 2.8.2, Mantine to 9.5.2, and Next.js to 16.3.2.

## 1.3.1 - 2026-08-23

- Reduced SQLite database lock errors in Docker by enabling a longer busy timeout and WAL mode.
- Prevented scheduled activity cleanup from running at the same time as the startup scan.
- Improved Docker dashboard/page responsiveness by avoiding full activity-history loads during startup and page navigation.
- Added database indexes for scan history, events, and notification history.

## 1.3.0 - 2026-08-23

- Moved Docker navigation into a sidebar and converted Settings into a full page.
- Added separate cleanup controls for events, scan history, and notification logs with retention settings.
- Added scheduled automatic cleanup for activity data, defaulting to 90 days.
- Improved the Home Map with persistent room nesting, layout reset confirmation, and clearer editing behavior.

## 1.2.0 - 2026-08-22

- Added a dedicated Docker Home Map view with room nesting, drag-and-drop layout editing, and device icons.
- Persisted Home Map layout preferences in the backend database.
- Added explicit Home Map layout saving with success and error notifications.
- Improved the Docker room visualization with cleaner spacing, offline icon styling, and reset confirmation.

## 1.1.7 - 2026-08-20

- Improved Docker mDNS hostname discovery by listening on the multicast group used by HomeKit/HAA devices.
- Added fallback coverage for Docker mDNS environments that cannot bind to multicast port 5353.
- Added a GitHub release downloads badge to the README.
- Replaced the README GIF preview with a clearer static dashboard image using fictional demo data.

## 1.1.6 - 2026-08-19

- Improved Docker HAA/HomeKit hostname discovery with repeated cached mDNS service probing.
- Prevented later hostname metadata from overwriting an already resolved hostname in the macOS scanner.
- Added regression coverage for hostname precedence in Docker and macOS.

## 1.1.5 - 2026-08-17

- Added public README demo media with fictional device data for screenshots and previews.
- Added Latest Scan detail views in Docker and macOS.
- Made Docker automatic scans wait the configured interval after the current scan completes.
- Improved role-aware risk scoring for known cameras, intercoms, and servers.
- Added clearer macOS inventory import/export feedback and Docker login greetings with full names.
- Updated the copy-paste Docker Compose example and Discord icon cache-busting.

## 1.1.4 - 2026-08-15

- Improved private/random MAC handling in Docker and macOS with clearer fallback names and labels.
- Avoided misleading vendor guesses for locally administered MAC addresses.
- Displayed Docker primary and secondary device icons together in device lists and map cards.
- Improved Docker ceiling-light icon rendering and fixed port badge layout in the device list.

## 1.1.3 - 2026-08-13

- Improved Docker hostname discovery for HomeKit/HAA devices through mDNS service answers.
- Added Docker device editing support for creating room names directly from the room field.
- Improved Apple private-MAC device recognition in the native macOS app.
- Reworked the native macOS Devices page to use clearer Docker-style device rows across full and narrow windows.

## 1.1.2 - 2026-08-13

- Improved Docker hostname discovery with LLMNR and cached SSDP/UPnP metadata lookup.
- Prevented unrelated multicast PTR answers from assigning the wrong hostname to other devices.
- Cleared stale read-only hostnames when the latest scan no longer resolves a valid hostname.
- Aligned macOS hostname safety checks with Docker for mDNS and reverse PTR responses.

## 1.0.22 - 2026-08-06

- Replaced bundled vendor lookup data with Wireshark manuf parsing and preserved original vendor names.
- Improved hostname discovery with DNS PTR, mDNS, LLMNR, NetBIOS, SSDP, HTTP metadata, HomeKit/HAA service discovery, and SNMP metadata.
- Refreshed read-only vendor and hostname fields on every scan, including known devices.
- Improved compact macOS dashboard cards and simplified the About window chrome.
- Cleaned Docker vendor handling to avoid manual brand aliases and stale vendor names.

## 1.0.21 - 2026-08-05

- Refined the native macOS About window into a compact, centered layout.
- Centered update status and clarified the update and release actions.
- Added About LanGuard access from the app menu and menu bar.

## 1.0.20 - 2026-08-05

- Added hostname discovery to native macOS network scans and preserved known hostnames when reverse lookup is unavailable.
- Improved Docker hostname lookup handling so unresolved names remain blank instead of producing misleading device names.
- Improved Docker inventory import compatibility for macOS exports, including dates, booleans, MAC addresses, roles, and rooms.
- Added room and role columns to the Docker device table.

## 1.0.19 - 2026-08-03

- Added Docker support for rooms, roles, hostnames, gateway metadata, and primary/secondary device icons.
- Made device import/export compatible between the Docker and native macOS applications.
- Added a centered native macOS update prompt with a direct release download action.

## 1.0.18 - 2026-08-02

- Added native macOS room support for devices, settings, import/export, filtering, and grouping views.
- Improved the macOS Devices page compact layout so search, filters, sorting, and the sidebar behave better in small windows.
- Preserved room assignments during device discovery merges.

## 1.0.17 - 2026-08-01

- Redesigned the native macOS About page with richer project details, support links, and a manual update check.
- Added GitHub release version checking for the native macOS app.
- Added icons to the macOS menu bar status items and quit action.

## 1.0.16 - 2026-07-30

- Fixed native macOS notification registration by signing the packaged app bundle with the stable LanGuard bundle identifier.
- Added explicit notification permission and notification settings actions in the macOS Settings page.
- Delayed notification permission prompts until the user enables or requests notifications from Settings.

## 1.0.15 - 2026-07-30

- Added the native macOS Grouping page for role-based device views.
- Added temporary Guest Scan so client or guest networks can be scanned without saving devices, history, or inventory changes.
- Added macOS device import/export, launch-at-login, an About page, menu bar status, and richer device detail editing.
- Improved macOS discovery with bundled vendor data, better role and icon detection, offline grace handling, and network/broadcast address filtering.
- Added more device icons, secondary device icons, manual role editing, and device deletion.
- Polished the macOS dashboard, Devices filters, compact layouts, sidebar behavior, and empty states across small and full-screen windows.

## 1.0.14 - 2026-07-29

- Published Docker backend and frontend images as multi-architecture builds for `linux/amd64` and `linux/arm64`.
- Fixed Portainer startup failures on non-Apple-Silicon hosts caused by single-architecture images.
- Added the version badge to the native macOS app header.

## 1.0.13 - 2026-07-29

- Added device inventory export and import for Docker LanGuard so device names, icons, vendors, IPs, MAC addresses, known state, and open ports can be moved between installs.
- Added matching device inventory export and import to the native macOS app settings.
- Updated the Docker project logo assets to use the improved LanGuard shield/network icon.
- Added the initial native macOS SwiftUI app source, packaging files, app icon, and tests under `macos/LanGuardMac`.

## 1.0.12 - 2026-07-14

- Updated backend dependencies through Dependabot, including Django 6.0.7 and drf-spectacular 0.30.0.
- Updated the frontend ESLint dependency through Dependabot.
- Improved the device table layout on mobile landscape and narrow tablet widths so columns use the compact mobile layout before they get cut off.

## 1.0.11 - 2026-07-11

- Fixed dashboard timestamps so timezone-less API dates are treated as UTC and displayed in the configured LanGuard timezone.
- Added automatic scan-status refresh for the Scan control and Latest scan panels without changing device table pagination.
- Standardized API and Discord notification timestamps to UTC ISO strings with a `Z` suffix.

## 1.0.10 - 2026-07-10

- Added gateway/router detection from the default network route and marks the gateway as a known router.
- Added device risk badges with backend risk scoring for unknown devices, risky ports, many open ports, missing vendors, and unstable scan status.

## 1.0.9 - 2026-07-08

- Fixed stale running scan records so newer completed scans show as finished instead of running.
- Added README guidance about private/random phone MAC addresses.

## 1.0.8 - 2026-07-05

- Added notification rules for new devices, online/offline changes, port changes, and quiet hours.
- Improved scan visibility with active/idle state, current range, duration, timing, and last error details.

## 1.0.7 - 2026-07-05

- Fixed device status filters so Offline, Online, Recently seen, and Sleeping use the same status field shown in the table.
- Aligned dashboard online/offline counters with the displayed device status.
- Added a settings option to configure new-version checks in minutes or hours.
- Updated frontend dependencies through Dependabot.
- Added Dependabot handling for Node Docker image major updates.

## 1.0.6 - 2026-07-04

- Improved online/offline status with status reasons, per-device grace, ICMP checks, and remembered-port confirmation.
- Added Dependabot updates and dependency review checks for GitHub pull requests.

## 1.0.5 - 2026-07-03

- Separated hubs and cameras into their own network map sections.
- Added smart hub, smart watch, LED strip, desk lamp, and ceiling light icons.
- Improved automatic icon detection for Aqara hubs and common lighting devices.
- Reworked device guessing into reusable backend rules using hostnames, vendors, and open ports.
- Improved vendor fallback names, including Foxconn and Espressif IoT devices, without adding MAC suffixes.
- Added a top-bar link to the LanGuard GitHub project.

## 1.0.4 - 2026-07-03

- Added a network map view with Internet, router, and device nodes.
- Added power strip, fan, ceiling fan, and separate shutter/blinds icons.
- Improved network map labels so long device names wrap cleanly.
- Cleaned up README badges for GHCR container images.

## 1.0.3 - 2026-07-01

- Added a new-version indicator that checks for published releases every 6 hours.
- Improved the mobile device list so phone screens no longer squeeze table columns.
- Added tablet, lock, and robot vacuum device icons.
- Cleaned up frontend Caddyfile formatting for quieter container startup logs.

## 1.0.0 - 2026-06-29

- Initial LanGuard release.
- Added light, dark, and auto theme modes.
- Added account management for admins and self-editing for regular users.
- Improved device editing with vendor, hostname, icon, and scan details.
- Improved scan results with hostname detection, safer device matching, and better notifications.
- Added top-bar version history and Docker image publishing support.
