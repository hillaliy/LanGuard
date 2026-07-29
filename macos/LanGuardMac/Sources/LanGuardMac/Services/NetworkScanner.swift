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
    private let sweepConcurrency: Int

    init(
        commandRunner: CommandRunning = CommandRunner(),
        portScanner: PortScanning = TCPPortScanner(),
        sweepConcurrency: Int = 32
    ) {
        self.commandRunner = commandRunner
        self.portScanner = portScanner
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

        let entries = ARPTableParser.parse(try await arpOutput)
            .filter { scanRange.contains($0.ipAddress) }
        let gatewayAddress = RouteParser.defaultGateway(from: (try? await routeOutput) ?? "")
        let seenAt = Date.now

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
                    scannedDevice.openPorts = await portScanner.scanOpenPorts(
                        host: device.ipAddress,
                        ports: settings.tcpPorts
                    )
                    scannedDevice.risk = DeviceRiskScorer.risk(
                        for: scannedDevice.openPorts,
                        isKnown: scannedDevice.isKnown
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
