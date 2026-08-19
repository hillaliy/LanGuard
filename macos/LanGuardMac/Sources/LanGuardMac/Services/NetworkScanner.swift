import Foundation

protocol NetworkScanning: Sendable {
    func scan(settings: AppSettings) async throws -> [NetworkDevice]
}

enum ScannerError: LocalizedError, Sendable {
    case commandFailed(String, String)
    case invalidScanRange(String)

    var errorDescription: String? {
        switch self {
        case let .commandFailed(command, output):
            "Command failed: \(command)\n\(output)"
        case let .invalidScanRange(range):
            "Invalid scan range: \(range)"
        }
    }
}

struct LocalNetworkScanner: NetworkScanning {
    private let commandRunner: CommandRunning
    private let portScanner: PortScanning
    private let metadataDiscovery: NetworkMetadataDiscovering
    private let metadataProbe: DeviceMetadataProbing
    private let sweepConcurrency: Int

    init(
        commandRunner: CommandRunning = CommandRunner(),
        portScanner: PortScanning = TCPPortScanner(),
        metadataDiscovery: NetworkMetadataDiscovering = DefaultNetworkMetadataDiscovery(),
        metadataProbe: DeviceMetadataProbing = HTTPDeviceMetadataProbe(),
        sweepConcurrency: Int = 32
    ) {
        self.commandRunner = commandRunner
        self.portScanner = portScanner
        self.metadataDiscovery = metadataDiscovery
        self.metadataProbe = metadataProbe
        self.sweepConcurrency = max(1, sweepConcurrency)
    }

    func scan(settings: AppSettings) async throws -> [NetworkDevice] {
        guard let scanRange = IPv4CIDRRange(settings.defaultScanRange) else {
            throw ScannerError.invalidScanRange(settings.defaultScanRange)
        }

        let hosts = scanRange.usableHosts()
        await sweep(hosts)
        await probeTCP(hosts, ports: settings.tcpPorts)

        async let arpOutput = commandRunner.run("/usr/sbin/arp", arguments: ["-a"])
        async let routeOutput = commandRunner.run("/sbin/route", arguments: ["-n", "get", "default"])

        let parsedEntries = ARPTableParser.parse(try await arpOutput)
            .filter { scanRange.isUsableHost($0.ipAddress) }
        let entries = await withTaskGroup(of: ARPEntry.self, returning: [ARPEntry].self) { group in
            for entry in parsedEntries {
                group.addTask {
                    var resolvedEntry = entry
                    if resolvedEntry.hostname?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty != false {
                        resolvedEntry.hostname = HostnameResolver.resolve(ipAddress: entry.ipAddress)
                    }
                    return resolvedEntry
                }
            }
            var resolvedEntries: [ARPEntry] = []
            for await entry in group { resolvedEntries.append(entry) }
            return resolvedEntries
        }
        let gatewayAddress = RouteParser.defaultGateway(from: (try? await routeOutput) ?? "")
        let seenAt = Date.now
        let discoveredMetadata = await metadataDiscovery.discoverMetadata(for: entries.map(\.ipAddress))

        let devices = entries.map { entry in
            NetworkDevice.discovered(
                hostname: entry.hostname,
                ipAddress: entry.ipAddress,
                macAddress: entry.macAddress,
                gatewayAddress: gatewayAddress,
                seenAt: seenAt
            )
        }

        return await withTaskGroup(of: NetworkDevice.self) { group in
            for device in devices {
                group.addTask {
                    var scannedDevice = device
                    let networkMetadata = discoveredMetadata[device.ipAddress]
                    scannedDevice.vendor = networkMetadata?.vendor ?? scannedDevice.vendor
                    scannedDevice.hostname = preferredHostname(
                        current: scannedDevice.hostname,
                        candidate: networkMetadata?.hostname
                    )
                    scannedDevice.openPorts = await portScanner.scanOpenPorts(
                        host: device.ipAddress,
                        ports: settings.tcpPorts
                    )
                    let metadata = await metadataProbe.probe(
                        host: device.ipAddress,
                        openPorts: scannedDevice.openPorts
                    )
                    scannedDevice.vendor = metadata.vendor ?? scannedDevice.vendor
                    scannedDevice.hostname = preferredHostname(
                        current: scannedDevice.hostname,
                        candidate: metadata.hostname
                    )
                    scannedDevice.risk = DeviceRiskScorer.risk(
                        for: scannedDevice.openPorts,
                        isKnown: scannedDevice.isKnown,
                        role: scannedDevice.role ?? .device
                    )
                    return DeviceProfiler.enrich(scannedDevice)
                }
            }

            var scannedDevices: [NetworkDevice] = []
            for await device in group {
                scannedDevices.append(device)
            }

            return scannedDevices.sorted { left, right in
                IPAddressSortKey(left.ipAddress) < IPAddressSortKey(right.ipAddress)
            }
        }
    }

    private func preferredHostname(
        current: String?,
        candidate: String?
    ) -> String? {
        if let current = HostnameResolver.clean(current) {
            return current
        }

        return HostnameResolver.clean(candidate)
    }

    private func sweep(_ hosts: [String]) async {
        for batchStart in stride(from: hosts.startIndex, to: hosts.endIndex, by: sweepConcurrency) {
            let batchEnd = min(batchStart + sweepConcurrency, hosts.endIndex)
            let batch = Array(hosts[batchStart..<batchEnd])

            await withTaskGroup(of: Void.self) { group in
                for host in batch {
                    group.addTask {
                        _ = try? await commandRunner.run(
                            "/sbin/ping",
                            arguments: ["-c", "1", "-W", "300", host]
                        )
                    }
                }
            }
        }
    }

    private func probeTCP(_ hosts: [String], ports: [Int]) async {
        guard !hosts.isEmpty, !ports.isEmpty else {
            return
        }

        for batchStart in stride(from: hosts.startIndex, to: hosts.endIndex, by: sweepConcurrency) {
            let batchEnd = min(batchStart + sweepConcurrency, hosts.endIndex)
            let batch = Array(hosts[batchStart..<batchEnd])

            await withTaskGroup(of: Void.self) { group in
                for host in batch {
                    group.addTask {
                        _ = await portScanner.scanOpenPorts(host: host, ports: ports)
                    }
                }
            }
        }
    }
}
