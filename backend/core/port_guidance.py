"""Version-controlled context and recommendations for commonly scanned ports."""

from dataclasses import dataclass


EXPECTED = "expected"
REVIEW = "review"
USUALLY_DISABLE = "usually_disable"

RECOMMENDATION_LABELS = {
    EXPECTED: "Expected",
    REVIEW: "Review",
    USUALLY_DISABLE: "Usually disable",
}


@dataclass(frozen=True)
class PortCatalogEntry:
    service_name: str
    common_uses: str
    recommendation: str
    recommendation_reason: str
    next_step: str
    expected_roles: frozenset[str] = frozenset()
    expected_icons: frozenset[str] = frozenset()
    attention_score: int = 0
    attention_exempt_roles: frozenset[str] = frozenset()
    attention_exempt_icons: frozenset[str] = frozenset()


PORT_CATALOG = {
    ("tcp", 21): PortCatalogEntry(
        service_name="FTP",
        common_uses="Legacy file transfer and device file management.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason="FTP normally sends credentials and data without encryption.",
        next_step="Disable FTP if it is not required, or prefer an encrypted transfer service.",
        attention_score=2,
    ),
    ("tcp", 22): PortCatalogEntry(
        service_name="SSH",
        common_uses="Encrypted command-line administration and secure file transfer.",
        recommendation=REVIEW,
        recommendation_reason="Remote administration should only be enabled on devices you manage.",
        next_step="Confirm SSH is intentional, uses strong authentication, and is limited to trusted clients.",
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
        attention_score=2,
        attention_exempt_roles=frozenset({"server"}),
        attention_exempt_icons=frozenset({"server"}),
    ),
    ("tcp", 23): PortCatalogEntry(
        service_name="Telnet",
        common_uses="Legacy command-line administration.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason="Telnet does not encrypt credentials or session traffic.",
        next_step="Disable Telnet and use SSH or the vendor's secure management option instead.",
        attention_score=3,
    ),
    ("tcp", 53): PortCatalogEntry(
        service_name="DNS",
        common_uses=(
            "Domain name resolution over TCP, including large responses, DNSSEC, "
            "and DNS zone transfers."
        ),
        recommendation=REVIEW,
        recommendation_reason=(
            "A DNS listener is expected on routers and DNS servers, but unusual on most client devices."
        ),
        next_step=(
            "Confirm the device intentionally provides DNS, restrict it to trusted clients, "
            "and disable the listener if it is not required."
        ),
        expected_roles=frozenset({"gateway", "router", "server"}),
        expected_icons=frozenset({"router", "server"}),
    ),
    ("tcp", 80): PortCatalogEntry(
        service_name="HTTP",
        common_uses="Local web interfaces, dashboards, APIs, and device setup pages.",
        recommendation=REVIEW,
        recommendation_reason="HTTP traffic is not encrypted, but local device interfaces commonly use it.",
        next_step="Keep it only when the device needs a local web interface; prefer HTTPS when available.",
        expected_roles=frozenset({"camera", "gateway", "hub", "intercom", "printer", "router", "server"}),
        expected_icons=frozenset({"printer", "router", "security-camera", "server", "smart-hub"}),
    ),
    ("tcp", 135): PortCatalogEntry(
        service_name="Windows RPC",
        common_uses="Windows remote procedure calls, service management, and administrative communication.",
        recommendation=REVIEW,
        recommendation_reason=(
            "Windows commonly uses RPC internally, but it should not be reachable from untrusted networks."
        ),
        next_step=(
            "Confirm the device runs Windows and restrict RPC access to trusted local clients with the host firewall."
        ),
        expected_roles=frozenset({"computer", "server"}),
        expected_icons=frozenset({"desktop", "laptop", "server"}),
    ),
    ("tcp", 139): PortCatalogEntry(
        service_name="NetBIOS Session Service",
        common_uses="Legacy Windows file and printer sharing using SMB over NetBIOS.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason=(
            "Modern SMB normally uses TCP port 445, so port 139 is usually only needed for legacy compatibility."
        ),
        next_step=(
            "Disable NetBIOS over TCP/IP when legacy sharing or discovery is not required; "
            "otherwise restrict it to trusted local devices."
        ),
    ),
    ("tcp", 443): PortCatalogEntry(
        service_name="HTTPS",
        common_uses="Encrypted web interfaces, dashboards, APIs, and device setup pages.",
        recommendation=REVIEW,
        recommendation_reason="An encrypted local management interface is common, but should still be intentional.",
        next_step="Confirm the interface belongs to this device and keep its software and credentials current.",
        expected_roles=frozenset({"camera", "gateway", "hub", "intercom", "printer", "router", "server"}),
        expected_icons=frozenset({"printer", "router", "security-camera", "server", "smart-hub"}),
    ),
    ("tcp", 515): PortCatalogEntry(
        service_name="LPD printing",
        common_uses="Legacy network printing through the Line Printer Daemon protocol.",
        recommendation=REVIEW,
        recommendation_reason="LPD is expected on some printers but is an older printing protocol.",
        next_step=(
            "Keep it only when a client requires LPD printing; otherwise prefer IPP and disable LPD."
        ),
        expected_roles=frozenset({"printer"}),
        expected_icons=frozenset({"printer"}),
    ),
    ("tcp", 548): PortCatalogEntry(
        service_name="AFP",
        common_uses="Legacy Apple file sharing and Time Machine access.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason=(
            "Modern Apple devices use SMB, so AFP is normally needed only for legacy compatibility."
        ),
        next_step="Disable AFP when older macOS clients or legacy Time Machine workflows do not require it.",
    ),
    ("tcp", 445): PortCatalogEntry(
        service_name="SMB",
        common_uses="Windows file and printer sharing, NAS access, and network discovery.",
        recommendation=REVIEW,
        recommendation_reason="SMB is useful for file sharing but is a frequent target when unnecessarily exposed.",
        next_step="Confirm file sharing is required; otherwise disable it and restrict access to trusted devices.",
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
        attention_score=3,
        attention_exempt_roles=frozenset({"server"}),
        attention_exempt_icons=frozenset({"server"}),
    ),
    ("tcp", 554): PortCatalogEntry(
        service_name="RTSP",
        common_uses="Live video and audio streams from cameras, intercoms, and media devices.",
        recommendation=REVIEW,
        recommendation_reason="RTSP is normal for video devices but unexpected on most other equipment.",
        next_step="Keep it for an intentional media stream and restrict viewers with device access controls.",
        expected_roles=frozenset({"camera", "intercom"}),
        expected_icons=frozenset({"security-camera"}),
    ),
    ("tcp", 631): PortCatalogEntry(
        service_name="IPP",
        common_uses="Network printing and printer status through the Internet Printing Protocol.",
        recommendation=REVIEW,
        recommendation_reason="IPP is expected on printers but unusual on unrelated devices.",
        next_step="Keep it when network printing is required; otherwise disable printer sharing.",
        expected_roles=frozenset({"printer"}),
        expected_icons=frozenset({"printer"}),
    ),
    ("tcp", 873): PortCatalogEntry(
        service_name="rsync",
        common_uses="File synchronization, backups, and replication between computers or storage servers.",
        recommendation=REVIEW,
        recommendation_reason=(
            "An rsync daemon can expose files when modules or network access are configured too broadly."
        ),
        next_step=(
            "Confirm the daemon is intentional, limit modules and clients, and use SSH transport when possible."
        ),
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
    ),
    ("tcp", 1883): PortCatalogEntry(
        service_name="MQTT",
        common_uses="Unencrypted messaging between IoT devices, home-automation services, and brokers.",
        recommendation=REVIEW,
        recommendation_reason=(
            "MQTT is common in local automation, but port 1883 does not encrypt credentials or messages."
        ),
        next_step=(
            "Keep it only for an intentional broker, require authentication, restrict clients, "
            "and prefer MQTT over TLS when supported."
        ),
        expected_roles=frozenset({"hub", "server"}),
        expected_icons=frozenset({"server", "smart-hub"}),
    ),
    ("tcp", 2049): PortCatalogEntry(
        service_name="NFS",
        common_uses="Unix and Linux network file sharing, NAS storage, and shared application data.",
        recommendation=REVIEW,
        recommendation_reason=(
            "NFS is useful for trusted storage clients but can expose files when exports are too broad."
        ),
        next_step=(
            "Review exported paths and client restrictions, and disable NFS when no trusted client requires it."
        ),
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
    ),
    ("tcp", 3389): PortCatalogEntry(
        service_name="Remote Desktop",
        common_uses="Microsoft Remote Desktop access to Windows computers and servers.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason="Remote desktop provides broad control of the device and should be tightly restricted.",
        next_step="Disable it when unused, or limit it to trusted clients with strong authentication.",
        expected_roles=frozenset({"computer", "server"}),
        expected_icons=frozenset({"desktop", "laptop", "server"}),
        attention_score=3,
    ),
    ("tcp", 5000): PortCatalogEntry(
        service_name="NAS/Web service",
        common_uses="NAS administration pages, local web applications, dashboards, and APIs.",
        recommendation=REVIEW,
        recommendation_reason=(
            "Port 5000 is used by several NAS and application products, so the port alone cannot identify the service."
        ),
        next_step=(
            "Confirm the interface belongs to the device and prefer its encrypted management port when available."
        ),
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
    ),
    ("tcp", 5001): PortCatalogEntry(
        service_name="Secure NAS/Web service",
        common_uses="Encrypted NAS administration pages, local web applications, dashboards, and APIs.",
        recommendation=REVIEW,
        recommendation_reason=(
            "Port 5001 is commonly used for encrypted NAS management, but other applications may also use it."
        ),
        next_step="Confirm the interface belongs to the device and keep its software and credentials current.",
        expected_roles=frozenset({"server"}),
        expected_icons=frozenset({"server"}),
    ),
    ("tcp", 5555): PortCatalogEntry(
        service_name="Android Debug Bridge",
        common_uses="Wireless Android debugging, device administration, and development access.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason=(
            "ADB provides powerful control of an Android device and should not remain available after debugging."
        ),
        next_step=(
            "Turn off wireless debugging or network ADB unless it is actively required, "
            "and revoke computers you do not recognize."
        ),
    ),
    ("tcp", 5900): PortCatalogEntry(
        service_name="VNC",
        common_uses="Remote graphical desktop access and screen sharing.",
        recommendation=USUALLY_DISABLE,
        recommendation_reason="VNC grants interactive access and older configurations may have weak protection.",
        next_step="Disable it when unused, or require strong authentication and trusted-network access.",
        expected_roles=frozenset({"computer", "server"}),
        expected_icons=frozenset({"desktop", "laptop", "server"}),
        attention_score=3,
    ),
    ("tcp", 8080): PortCatalogEntry(
        service_name="Web/API service",
        common_uses="Alternate web interfaces, local APIs, proxies, and application dashboards.",
        recommendation=REVIEW,
        recommendation_reason="Port 8080 has many possible uses, so the port number alone cannot identify the service.",
        next_step="Open the service only if you recognize it, then check the device documentation and access controls.",
        expected_roles=frozenset({"camera", "intercom", "server"}),
        expected_icons=frozenset({"security-camera", "server", "smart-hub"}),
        attention_score=2,
        attention_exempt_roles=frozenset({"camera", "intercom", "server"}),
        attention_exempt_icons=frozenset({"security-camera", "server"}),
    ),
    ("tcp", 8123): PortCatalogEntry(
        service_name="Home Assistant",
        common_uses="Home Assistant's local web interface, API, dashboards, and automation control.",
        recommendation=REVIEW,
        recommendation_reason=(
            "Port 8123 commonly belongs to Home Assistant, but another application can use the same port."
        ),
        next_step=(
            "Confirm this is the intended Home Assistant instance, require authentication, "
            "and avoid direct Internet exposure."
        ),
        expected_roles=frozenset({"hub", "server"}),
        expected_icons=frozenset({"server", "smart-hub"}),
    ),
    ("tcp", 8443): PortCatalogEntry(
        service_name="Alternate HTTPS/API service",
        common_uses="Alternate encrypted web interfaces, local APIs, and application dashboards.",
        recommendation=REVIEW,
        recommendation_reason="Port 8443 is commonly used for HTTPS, but the port number does not prove the protocol or product.",
        next_step="Verify the service in the device documentation and keep it only when the interface is required.",
        expected_roles=frozenset({"camera", "intercom", "server"}),
        expected_icons=frozenset({"security-camera", "server", "smart-hub"}),
    ),
    ("tcp", 8883): PortCatalogEntry(
        service_name="MQTT over TLS",
        common_uses="Encrypted messaging between IoT devices, home-automation services, and brokers.",
        recommendation=REVIEW,
        recommendation_reason=(
            "Encrypted MQTT is appropriate for an intentional broker but should still require trusted clients."
        ),
        next_step=(
            "Confirm the broker is intentional, require authentication, and keep certificates and software current."
        ),
        expected_roles=frozenset({"hub", "server"}),
        expected_icons=frozenset({"server", "smart-hub"}),
    ),
    ("tcp", 9100): PortCatalogEntry(
        service_name="RAW printing",
        common_uses="Direct network printing, often called JetDirect or RAW printing.",
        recommendation=REVIEW,
        recommendation_reason="This is expected on many printers but should not normally appear on other devices.",
        next_step="Keep it for direct network printing; otherwise disable RAW or JetDirect printing.",
        expected_roles=frozenset({"printer"}),
        expected_icons=frozenset({"printer"}),
    ),
}


def _port_value(port, name, default=""):
    if isinstance(port, dict):
        return port.get(name, default)
    return getattr(port, name, default)


def port_guidance(device, port):
    protocol = str(_port_value(port, "protocol", "tcp") or "tcp").lower()
    port_number = int(_port_value(port, "port", 0) or 0)
    entry = PORT_CATALOG.get((protocol, port_number))
    registry_service = str(_port_value(port, "service", "") or "").strip()
    if entry is None:
        service_name = registry_service or "Unidentified service"
        return {
            "service_name": service_name,
            "common_uses": (
                "LanGuard does not yet have specific guidance for this port. "
                "The application using it may be device-specific."
            ),
            "recommendation": REVIEW,
            "recommendation_label": RECOMMENDATION_LABELS[REVIEW],
            "context": (
                "The port number alone is not enough to identify the application or decide whether it is safe."
            ),
            "next_step": (
                "Check the device documentation and disable the service if you do not recognize or need it."
            ),
            "identification_basis": "port_mapping",
            "identification_label": "Identified from the port number",
            "registry_service": registry_service,
            "scope_notice": (
                "LanGuard found this port reachable on the local network. "
                "This does not show whether it is exposed to the Internet."
            ),
        }

    role = str(getattr(device, "role", "") or "").strip().lower()
    icon = str(getattr(device, "icon", "") or "").strip().lower()
    known = bool(getattr(device, "known", False))
    context_matches = known and (
        role in entry.expected_roles or icon in entry.expected_icons
    )
    recommendation = EXPECTED if context_matches else entry.recommendation

    if context_matches:
        context = (
            f"This port is commonly associated with a device classified as "
            f"{role or icon.replace('-', ' ')}."
        )
    else:
        context = entry.recommendation_reason

    return {
        "service_name": entry.service_name,
        "common_uses": entry.common_uses,
        "recommendation": recommendation,
        "recommendation_label": RECOMMENDATION_LABELS[recommendation],
        "context": context,
        "next_step": entry.next_step,
        "identification_basis": "port_mapping",
        "identification_label": "Identified from the port number",
        "registry_service": registry_service,
        "scope_notice": (
            "LanGuard found this port reachable on the local network. "
            "This does not show whether it is exposed to the Internet."
        ),
    }


def port_attention(device, port):
    protocol = str(_port_value(port, "protocol", "tcp") or "tcp").lower()
    port_number = int(_port_value(port, "port", 0) or 0)
    entry = PORT_CATALOG.get((protocol, port_number))
    if entry is None or not entry.attention_score:
        return None

    role = str(getattr(device, "role", "") or "").strip().lower()
    icon = str(getattr(device, "icon", "") or "").strip().lower()
    if getattr(device, "known", False) and (
        role in entry.attention_exempt_roles
        or icon in entry.attention_exempt_icons
    ):
        return None

    guidance = port_guidance(device, port)
    return {
        "score": entry.attention_score,
        "high_risk": entry.attention_score >= 3,
        "label": entry.service_name,
        "next_step": guidance["next_step"],
    }
