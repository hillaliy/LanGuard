import Testing
@testable import LanGuardMac

private struct StubCommandRunner: CommandRunning {
    func run(_ launchPath: String, arguments: [String]) async throws -> String {
        switch launchPath {
        case "/usr/sbin/arp":
            """
            router.local (192.168.0.1) at 1:2:3:a:b:c on en0 ifscope [ethernet]
            camera.local (192.168.0.20) at 90:dd:5d:b7:bd:01 on en0 ifscope [ethernet]
            broadcast (192.168.0.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]
            """
        case "/sbin/route":
            """
               route to: default
            destination: default
                   mask: default
                gateway: 192.168.0.1
              interface: en0
            """
        default:
            ""
        }
    }
}

private struct StubPortScanner: PortScanning {
    func scanOpenPorts(host: String, ports: [Int]) async -> [Int] {
        switch host {
        case "192.168.0.1":
            [53, 80]
        case "192.168.0.20":
            [80, 554, 8443]
        default:
            []
        }
    }
}

private struct StubMetadataProbe: DeviceMetadataProbing {
    func probe(host: String, openPorts: [Int]) async -> DeviceMetadata {
        switch host {
        case "192.168.0.20":
            DeviceMetadata(vendor: "Reolink")
        default:
            DeviceMetadata()
        }
    }
}

private struct StubNetworkMetadataDiscovery: NetworkMetadataDiscovering {
    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        [
            "192.168.0.20": DeviceMetadata(
                vendor: "Hangzhou Hikvision Digital Technology Co., Ltd.",
                hostname: "Front Door Camera"
            )
        ]
    }
}

private struct HostnameMetadataDiscovery: NetworkMetadataDiscovering {
    let ipAddress: String
    let hostname: String

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        [
            ipAddress: DeviceMetadata(hostname: hostname)
        ]
    }
}

private struct AppleARPCommandRunner: CommandRunning {
    func run(_ launchPath: String, arguments: [String]) async throws -> String {
        switch launchPath {
        case "/usr/sbin/arp":
            "iphone.local (192.168.0.30) at 90:dd:5d:b7:bd:01 on en0 ifscope [ethernet]"
        case "/sbin/route":
            "gateway: 192.168.0.1"
        default:
            ""
        }
    }
}

private struct PrivateAddressARPCommandRunner: CommandRunning {
    func run(_ launchPath: String, arguments: [String]) async throws -> String {
        switch launchPath {
        case "/usr/sbin/arp":
            "? (192.168.0.31) at c6:f5:3a:d8:da:f0 on en0 ifscope [ethernet]"
        case "/sbin/route":
            "gateway: 192.168.0.1"
        default:
            ""
        }
    }
}

private struct EmptyNetworkMetadataDiscovery: NetworkMetadataDiscovering {
    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        [:]
    }
}

private struct EmptyMetadataProbe: DeviceMetadataProbing {
    func probe(host: String, openPorts: [Int]) async -> DeviceMetadata {
        DeviceMetadata()
    }
}

private actor RecordingPortScanner: PortScanning {
    private var scannedHosts: [String] = []

    func scanOpenPorts(host: String, ports: [Int]) async -> [Int] {
        scannedHosts.append(host)
        return []
    }

    func hosts() -> [String] {
        scannedHosts
    }
}

@Test
func localScannerAddsOpenPortsGatewayAndRisk() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: EmptyNetworkMetadataDiscovery(),
        metadataProbe: StubMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: [53, 80, 554, 8443],
        scheduledScanningEnabled: false
    ))

    #expect(devices.count == 2)
    #expect(devices.first?.ipAddress == "192.168.0.1")
    #expect(devices.first?.isGateway == true)
    #expect(devices.first?.openPorts == [53, 80])
    #expect(devices.first?.risk == .medium)
    #expect(devices.last?.ipAddress == "192.168.0.20")
    #expect(devices.last?.vendor == "Reolink")
    #expect(devices.last?.openPorts == [80, 554, 8443])
    #expect(devices.last?.risk == .medium)
}

@Test
func localScannerFiltersDevicesOutsideConfiguredRange() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: EmptyNetworkMetadataDiscovery(),
        metadataProbe: EmptyMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/30",
        scanIntervalMinutes: 5,
        tcpPorts: [53, 80],
        scheduledScanningEnabled: false
    ))

    #expect(devices.map(\.ipAddress) == ["192.168.0.1"])
}

@Test
func localScannerFiltersNetworkBroadcastARPEntries() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: EmptyNetworkMetadataDiscovery(),
        metadataProbe: EmptyMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: [53, 80],
        scheduledScanningEnabled: false
    ))

    #expect(devices.map(\.ipAddress).contains("192.168.0.255") == false)
}

@Test
func localScannerRejectsInvalidScanRange() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: EmptyNetworkMetadataDiscovery(),
        metadataProbe: EmptyMetadataProbe()
    )

    await #expect(throws: ScannerError.self) {
        _ = try await scanner.scan(settings: AppSettings(
            defaultScanRange: "not-a-range",
            scanIntervalMinutes: 5,
            tcpPorts: [80],
            scheduledScanningEnabled: false
        ))
    }
}

@Test
func localScannerProbesTCPHostsBeforeReadingFilteredDevices() async throws {
    let portScanner = RecordingPortScanner()
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: portScanner,
        metadataDiscovery: EmptyNetworkMetadataDiscovery(),
        metadataProbe: EmptyMetadataProbe(),
        sweepConcurrency: 2
    )

    _ = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/30",
        scanIntervalMinutes: 5,
        tcpPorts: [80],
        scheduledScanningEnabled: false
    ))

    #expect(await portScanner.hosts().contains("192.168.0.2"))
}

@Test
func localScannerUsesNetworkMetadataDiscoveryBeforePerDeviceProbe() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: StubCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: StubNetworkMetadataDiscovery(),
        metadataProbe: EmptyMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: [80, 554],
        scheduledScanningEnabled: false
    ))

    let camera = try #require(devices.first { $0.ipAddress == "192.168.0.20" })
    #expect(camera.hostname == "camera")
    #expect(camera.vendor == "Hangzhou Hikvision Digital Technology Co., Ltd.")
}

@Test
func localScannerDoesNotReplaceExistingHostnameWithNetworkMetadataHostname() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: AppleARPCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: HostnameMetadataDiscovery(
            ipAddress: "192.168.0.30",
            hostname: "living-room-speaker"
        ),
        metadataProbe: EmptyMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: [80],
        scheduledScanningEnabled: false
    ))

    let iphone = try #require(devices.first { $0.ipAddress == "192.168.0.30" })
    #expect(iphone.hostname == "iphone")
}

@Test
func localScannerUsesNetworkMetadataHostnameWhenCurrentHostnameIsMissing() async throws {
    let scanner = LocalNetworkScanner(
        commandRunner: PrivateAddressARPCommandRunner(),
        portScanner: StubPortScanner(),
        metadataDiscovery: HostnameMetadataDiscovery(
            ipAddress: "192.168.0.31",
            hostname: "HAA-123456"
        ),
        metadataProbe: EmptyMetadataProbe()
    )

    let devices = try await scanner.scan(settings: AppSettings(
        defaultScanRange: "192.168.0.0/24",
        scanIntervalMinutes: 5,
        tcpPorts: [80],
        scheduledScanningEnabled: false
    ))

    let device = try #require(devices.first { $0.ipAddress == "192.168.0.31" })
    #expect(device.hostname == "HAA 123456")
}
