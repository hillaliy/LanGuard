# Network Map

The main map displays infrastructure: routers, mesh routers, switches, access
points, network hubs and smart-home hubs. Devices are classified using their saved
role/icon or known gateway flag, not their name or IP range. Only existing
connections between infrastructure nodes are drawn. This does not change or delete
any saved endpoint connections.

Select an infrastructure node to open its directly connected devices. The table
supports search, status/connection/device-type filters, device-page navigation and
connection inspection. Upstream infrastructure peers can also appear in this
direct-connection list; it is not a recursive list of all downstream clients.
Multiple physical links to the same logical device remain individually accessible.

Phones, tablets, laptops and watches are grouped automatically from their saved
type/icon. Presence comes from the inventory scan results. A mobile device without
a saved connection is shown with an unknown access point. Neither a mobile type
nor a shared subnet proves Wi-Fi, an access point, a smart-home radio association
or a roaming event. LLDP evidence and explicit user assignments remain distinct.

Desktop/tablet maps display mobile devices in per-infrastructure/per-transport
groups. Only saved associations produce group connection lines. Unassigned mobile
devices have a separate group with no invented uplink. On phones, the mobile
summary stays above the canvas. Solid lines represent Ethernet, dashed lines
Wi-Fi, and dotted lines unknown transport. Aggregated mobile links have a mobile
icon and a dash-dot Wi-Fi pattern. Evidence color and stale opacity remain separate.
Disconnected infrastructure components are packed into a compact multi-column
layout; the unconnected inventory can be toggled to give the canvas its full width.

Use the Internet globe action to add a manual uplink to an inventoried network
interface. The globe is a virtual map node, not a scanner device or a live Internet
availability probe. Its connection type and target can be changed by selecting
the globe or its line. Removing it leaves the inventory and physical device links
unchanged. An archived/deleted target is shown as unavailable rather than guessed.
These edits use the same background queue and revision checks as other map edits.
When Speedtest Tracker is enabled and configured, the tile reuses the existing
integration payload to show download/upload Mbps, ping, packet loss and test time.
A completed positive speed test within 15 minutes is marked verified at test time;
threshold failures are degraded, older results historical, and an unavailable API
unverified rather than offline. This is not a probe of the selected WAN path.
No additional calls or new bandwidth tests run as part of map loading.

The illustrated public guide is maintained in `website/docs/network-map.mdx`.

An arrow-shuffle roaming indicator denotes mobile devices without a fixed router
assignment; its tooltip explicitly states that actual roaming was not detected.
Saved connections can be edited directly from their line drawer or the pencil
actions in a node's device table; entering layout-edit mode is not required.

## Background Saves

The browser submits map changes to `POST /api/v1/network-map/commands/` with a
UUID request ID, operation path, method and body. A `202` response means the
request is durably queued, not that its changes are already applied. Repeating
the same user/request ID returns the same command; changing its payload is
rejected. Queue history is private to the requesting user and is available at
`GET /api/v1/network-map/commands/` (pending and recent completed requests).

The scheduler processes commands under the shared writer lock. Applying the
mutation and marking the command completed happen in one database transaction.
An interrupted transaction rolls back, leaving the command queued for the next
worker. All bulk changes are atomic. Current permissions, inventory membership,
duplicate checks and revision conflicts are checked again at execution. Conflicts
are reported rather than overwriting newer edits. Other users' edits may still
cause a queued operation to fail; its original body and failure reason remain in
the requesting user's history.

Queue intake bypasses the long cooperative scan lock but still obeys SQLite's
own write locks. Brief SQLite contention is retried with bounded waits. If intake
cannot be confirmed (for example, a server outage), the browser retains the form
and does not claim the operation was saved. Retrying an uncertain intake uses the
same request ID. The browser polls pending results and restores pending layout
positions after a refresh. There is only one saved layout. A one-time upgrade
consolidates existing infrastructure positions into it, or clears obsolete
full-inventory coordinates so the new compact layout is generated automatically.
Existing physical connections, device assignments and LLDP evidence are unchanged.

In Docker, the existing scheduler runs the worker; no extra service is required.
For local development without network scans or integration syncs, run:

```sh
.venv/bin/python backend/manage.py migrate
.venv/bin/python backend/manage.py run_network_map_queue
```
