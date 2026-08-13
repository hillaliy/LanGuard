import Darwin
import Foundation

protocol NetworkMetadataDiscovering: Sendable {
    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata]
}

struct DisabledNetworkMetadataDiscovery: NetworkMetadataDiscovering {
    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        [:]
    }
}

struct DefaultNetworkMetadataDiscovery: NetworkMetadataDiscovering {
    private let dnsDiscovery: DNSPTRMetadataDiscovery
    private let ssdpDiscovery: SSDPMetadataDiscovery
    private let mdnsDiscovery: MDNSReverseMetadataDiscovery
    private let mdnsSocketDiscovery: MDNSPTRSocketDiscovery
    private let mdnsServiceDiscovery: MDNSServiceMetadataDiscovery
    private let llmnrDiscovery: LLMNRReverseMetadataDiscovery
    private let netBIOSDiscovery: NetBIOSNameDiscovery
    private let snmpDiscovery: SNMPMetadataDiscovery

    init(
        dnsDiscovery: DNSPTRMetadataDiscovery = DNSPTRMetadataDiscovery(),
        ssdpDiscovery: SSDPMetadataDiscovery = SSDPMetadataDiscovery(),
        mdnsDiscovery: MDNSReverseMetadataDiscovery = MDNSReverseMetadataDiscovery(),
        mdnsSocketDiscovery: MDNSPTRSocketDiscovery = MDNSPTRSocketDiscovery(),
        mdnsServiceDiscovery: MDNSServiceMetadataDiscovery = MDNSServiceMetadataDiscovery(),
        llmnrDiscovery: LLMNRReverseMetadataDiscovery = LLMNRReverseMetadataDiscovery(),
        netBIOSDiscovery: NetBIOSNameDiscovery = NetBIOSNameDiscovery(),
        snmpDiscovery: SNMPMetadataDiscovery = SNMPMetadataDiscovery()
    ) {
        self.dnsDiscovery = dnsDiscovery
        self.ssdpDiscovery = ssdpDiscovery
        self.mdnsDiscovery = mdnsDiscovery
        self.mdnsSocketDiscovery = mdnsSocketDiscovery
        self.mdnsServiceDiscovery = mdnsServiceDiscovery
        self.llmnrDiscovery = llmnrDiscovery
        self.netBIOSDiscovery = netBIOSDiscovery
        self.snmpDiscovery = snmpDiscovery
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        async let dnsMetadata = dnsDiscovery.discoverMetadata(for: ipAddresses)
        async let ssdpMetadata = ssdpDiscovery.discoverMetadata(for: ipAddresses)
        async let mdnsMetadata = mdnsDiscovery.discoverMetadata(for: ipAddresses)
        async let mdnsSocketMetadata = mdnsSocketDiscovery.discoverMetadata(for: ipAddresses)
        async let mdnsServiceMetadata = mdnsServiceDiscovery.discoverMetadata(for: ipAddresses)
        async let llmnrMetadata = llmnrDiscovery.discoverMetadata(for: ipAddresses)
        async let netBIOSMetadata = netBIOSDiscovery.discoverMetadata(for: ipAddresses)
        async let snmpMetadata = snmpDiscovery.discoverMetadata(for: ipAddresses)
        var combined = await dnsMetadata

        for (ipAddress, metadata) in await mdnsMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await mdnsSocketMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await mdnsServiceMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await ssdpMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await netBIOSMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await llmnrMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        for (ipAddress, metadata) in await snmpMetadata {
            combined[ipAddress] = combined[ipAddress]?.merged(with: metadata) ?? metadata
        }

        return combined
    }
}

struct DNSPTRMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeoutSeconds: Int
    private let concurrency: Int

    init(timeoutSeconds: Int = 1, concurrency: Int = 16) {
        self.timeoutSeconds = max(1, timeoutSeconds)
        self.concurrency = max(1, concurrency)
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        var metadataByIP: [String: DeviceMetadata] = [:]
        let uniqueIPs = Array(Set(ipAddresses)).sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

        for batchStart in stride(from: uniqueIPs.startIndex, to: uniqueIPs.endIndex, by: concurrency) {
            let batchEnd = min(batchStart + concurrency, uniqueIPs.endIndex)
            let batch = Array(uniqueIPs[batchStart..<batchEnd])

            await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
                for ipAddress in batch {
                    group.addTask {
                        guard let hostname = await resolveHostname(ipAddress: ipAddress, timeoutSeconds: timeoutSeconds) else {
                            return nil
                        }
                        return (ipAddress, DeviceMetadata(vendor: nil, hostname: hostname))
                    }
                }

                for await result in group {
                    guard let (ipAddress, metadata) = result else { continue }
                    metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
                }
            }
        }

        return metadataByIP
    }

    static func hostname(fromDigOutput output: String, ipAddress: String) -> String? {
        output
            .components(separatedBy: .newlines)
            .lazy
            .compactMap { HostnameResolver.clean($0, ipAddress: ipAddress) }
            .first
    }

    private func resolveHostname(ipAddress: String, timeoutSeconds: Int) async -> String? {
        await Task.detached(priority: .utility) {
            let process = Process()
            let pipe = Pipe()

            process.executableURL = URL(fileURLWithPath: "/usr/bin/dig")
            process.arguments = ["+short", "+time=\(timeoutSeconds)", "+tries=1", "-x", ipAddress]
            process.standardOutput = pipe
            process.standardError = pipe

            do {
                try process.run()
            } catch {
                return nil
            }

            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return Self.hostname(fromDigOutput: output, ipAddress: ipAddress)
        }.value
    }
}

struct SNMPMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeoutSeconds: Double
    private let concurrency: Int
    private let community: String

    init(timeoutSeconds: Double = 0.4, concurrency: Int = 16, community: String = "public") {
        self.timeoutSeconds = max(0.2, timeoutSeconds)
        self.concurrency = max(1, concurrency)
        self.community = community
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        guard FileManager.default.isExecutableFile(atPath: "/usr/bin/snmpget") else {
            return [:]
        }

        var metadataByIP: [String: DeviceMetadata] = [:]
        let uniqueIPs = Array(Set(ipAddresses)).sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

        for batchStart in stride(from: uniqueIPs.startIndex, to: uniqueIPs.endIndex, by: concurrency) {
            let batchEnd = min(batchStart + concurrency, uniqueIPs.endIndex)
            let batch = Array(uniqueIPs[batchStart..<batchEnd])

            await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
                for ipAddress in batch {
                    group.addTask {
                        let metadata = await metadata(ipAddress: ipAddress)
                        guard metadata.hostname != nil || metadata.vendor != nil else {
                            return nil
                        }
                        return (ipAddress, metadata)
                    }
                }

                for await result in group {
                    guard let (ipAddress, metadata) = result else { continue }
                    metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
                }
            }
        }

        return metadataByIP
    }

    static func metadata(sysName: String?, sysDescr: String?, ipAddress: String = "") -> DeviceMetadata {
        DeviceMetadata(
            vendor: cleanedSNMPValue(sysDescr),
            hostname: HostnameResolver.clean(cleanedSNMPValue(sysName), ipAddress: ipAddress)
        )
    }

    private func metadata(ipAddress: String) async -> DeviceMetadata {
        async let sysName = snmpValue(ipAddress: ipAddress, oid: "1.3.6.1.2.1.1.5.0")
        async let sysDescr = snmpValue(ipAddress: ipAddress, oid: "1.3.6.1.2.1.1.1.0")
        return Self.metadata(sysName: await sysName, sysDescr: await sysDescr, ipAddress: ipAddress)
    }

    private func snmpValue(ipAddress: String, oid: String) async -> String? {
        await Task.detached(priority: .utility) {
            let process = Process()
            let pipe = Pipe()

            process.executableURL = URL(fileURLWithPath: "/usr/bin/snmpget")
            process.arguments = [
                "-v", "2c",
                "-c", community,
                "-t", String(format: "%.1f", timeoutSeconds),
                "-r", "0",
                "-Oqv",
                ipAddress,
                oid,
            ]
            process.standardOutput = pipe
            process.standardError = pipe

            do {
                try process.run()
            } catch {
                return nil
            }

            process.waitUntilExit()
            guard process.terminationStatus == 0 else { return nil }

            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return Self.cleanedSNMPValue(output)
        }.value
    }

    private static func cleanedSNMPValue(_ value: String?) -> String? {
        let cleaned = (value ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: #""""#))
        let lowered = cleaned.lowercased()
        guard !cleaned.isEmpty,
              cleaned != "-",
              lowered != "no such object available on this agent at this oid",
              lowered != "no such instance currently exists at this oid",
              !lowered.contains("timeout"),
              !lowered.contains("no response"),
              !lowered.contains("unknown host") else {
            return nil
        }
        return cleaned
    }
}

struct SSDPMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval

    init(timeout: TimeInterval = 1.2) {
        self.timeout = timeout
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        let allowedIPs = Set(ipAddresses)
        let responses = await SSDPSocketClient(timeout: timeout).discover()
        var metadataByIP: [String: DeviceMetadata] = [:]

        await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
            for response in responses {
                guard allowedIPs.isEmpty || allowedIPs.contains(response.ipAddress) else { continue }
                group.addTask {
                    let metadata = await Self.metadata(from: response)
                    guard metadata.vendor != nil || metadata.hostname != nil else {
                        return nil
                    }
                    return (response.ipAddress, metadata)
                }
            }

            for await result in group {
                guard let (ipAddress, metadata) = result else { continue }
                metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
            }
        }

        return metadataByIP
    }

    static func metadata(from response: SSDPResponse) async -> DeviceMetadata {
        let serverVendor = explicitVendor(fromServerHeader: response.headers["server"])
        var metadata = DeviceMetadata(
            vendor: MACVendorResolver.displayVendor(serverVendor),
            hostname: nil
        )

        if let location = response.headers["location"],
           let url = URL(string: location),
           let description = await fetchDeviceDescription(from: url) {
            metadata = metadata.merged(with: description)
        }

        return metadata
    }

    static func metadata(fromDeviceDescription body: String) -> DeviceMetadata {
        let manufacturer = firstXMLValue(in: body, tag: "manufacturer")
        let friendlyName = firstXMLValue(in: body, tag: "friendlyName")
        let modelName = firstXMLValue(in: body, tag: "modelName")
        let hostname = HostnameResolver.clean(friendlyName ?? modelName, ipAddress: "")

        return DeviceMetadata(
            vendor: MACVendorResolver.displayVendor(manufacturer),
            hostname: hostname
        )
    }

    private static func fetchDeviceDescription(from url: URL) async -> DeviceMetadata? {
        var request = URLRequest(url: url)
        request.timeoutInterval = 1.5
        request.setValue("LanGuard/1.0", forHTTPHeaderField: "User-Agent")

        do {
            let (data, _) = try await URLSession.shared.data(for: request)
            let body = String(data: data.prefix(128_000), encoding: .utf8) ?? ""
            return metadata(fromDeviceDescription: body)
        } catch {
            return nil
        }
    }

    private static func explicitVendor(fromServerHeader server: String?) -> String? {
        guard let server else { return nil }
        let parts = server
            .split(separator: " ")
            .map { $0.trimmingCharacters(in: CharacterSet(charactersIn: ",;")) }
            .filter { !$0.isEmpty }

        guard let first = parts.first else { return nil }
        let lowered = first.lowercased()
        if lowered.contains("/") || lowered == "upnp" || lowered.hasPrefix("posix") {
            return nil
        }
        return first
    }

    private static func firstXMLValue(in body: String, tag: String) -> String? {
        let escapedTag = NSRegularExpression.escapedPattern(for: tag)
        guard
            let regex = try? NSRegularExpression(
                pattern: #"<\#(escapedTag)>\s*([^<]+)\s*</\#(escapedTag)>"#,
                options: [.caseInsensitive]
            )
        else {
            return nil
        }

        let range = NSRange(body.startIndex..<body.endIndex, in: body)
        guard
            let match = regex.firstMatch(in: body, range: range),
            let matchRange = Range(match.range(at: 1), in: body)
        else {
            return nil
        }

        let value = body[matchRange]
            .replacingOccurrences(of: "&amp;", with: "&")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }
}

struct MDNSReverseMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval
    private let concurrency: Int

    init(timeout: TimeInterval = 0.8, concurrency: Int = 12) {
        self.timeout = timeout
        self.concurrency = max(1, concurrency)
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        var metadataByIP: [String: DeviceMetadata] = [:]
        let uniqueIPs = Array(Set(ipAddresses)).sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

        for batchStart in stride(from: uniqueIPs.startIndex, to: uniqueIPs.endIndex, by: concurrency) {
            let batchEnd = min(batchStart + concurrency, uniqueIPs.endIndex)
            let batch = Array(uniqueIPs[batchStart..<batchEnd])

            await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
                for ipAddress in batch {
                    group.addTask {
                        guard let hostname = await resolveHostname(ipAddress: ipAddress, timeout: timeout) else {
                            return nil
                        }
                        return (ipAddress, DeviceMetadata(vendor: nil, hostname: hostname))
                    }
                }

                for await result in group {
                    guard let (ipAddress, metadata) = result else { continue }
                    metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
                }
            }
        }

        return metadataByIP
    }

    static func hostname(from output: String, ipAddress: String) -> String? {
        let expectedOwner = reversePTRQuery(for: ipAddress)
        for line in output.components(separatedBy: .newlines) {
            let fields = line.split(whereSeparator: \.isWhitespace).map(String.init)
            guard
                let ptrIndex = fields.firstIndex(where: { $0.caseInsensitiveCompare("PTR") == .orderedSame }),
                fields.indices.contains(ptrIndex + 1)
            else {
                continue
            }

            if let expectedOwner,
               let owner = fields.prefix(ptrIndex).last,
               normalizedDNSName(owner) != normalizedDNSName(expectedOwner) {
                continue
            }

            let candidates = fields[(ptrIndex + 1)...].filter { field in
                let lowered = field.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "."))
                return lowered != "in"
                    && lowered != "internet"
                    && lowered != "flush"
                    && lowered != "cache"
                    && !lowered.allSatisfy(\.isNumber)
            }

            for candidate in candidates {
                guard candidate.contains(".") || candidate.contains("-") else { continue }
                if let hostname = HostnameResolver.clean(candidate, ipAddress: ipAddress) {
                    return hostname
                }
            }
        }
        return nil
    }

    private static func reversePTRQuery(for ipAddress: String) -> String? {
        let parts = ipAddress.split(separator: ".")
        guard parts.count == 4, parts.allSatisfy({ UInt8($0) != nil }) else {
            return nil
        }
        return parts.reversed().joined(separator: ".") + ".in-addr.arpa"
    }

    private static func normalizedDNSName(_ value: String) -> String {
        value.trimmingCharacters(in: CharacterSet(charactersIn: ".")).lowercased()
    }

    private func resolveHostname(ipAddress: String, timeout: TimeInterval) async -> String? {
        guard let query = reversePTRQuery(for: ipAddress) else { return nil }

        return await Task.detached(priority: .utility) {
            let process = Process()
            let pipe = Pipe()

            process.executableURL = URL(fileURLWithPath: "/usr/bin/dns-sd")
            process.arguments = ["-q", query, "PTR"]
            process.standardOutput = pipe
            process.standardError = pipe

            do {
                try process.run()
            } catch {
                return nil
            }

            DispatchQueue.global(qos: .utility).asyncAfter(deadline: .now() + timeout) {
                if process.isRunning {
                    process.terminate()
                }
            }

            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let output = String(data: data, encoding: .utf8) ?? ""
            return Self.hostname(from: output, ipAddress: ipAddress)
        }.value
    }

    private func reversePTRQuery(for ipAddress: String) -> String? {
        let parts = ipAddress.split(separator: ".")
        guard parts.count == 4, parts.allSatisfy({ UInt8($0) != nil }) else {
            return nil
        }
        return parts.reversed().joined(separator: ".") + ".in-addr.arpa"
    }
}

struct MDNSPTRSocketDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval
    private let concurrency: Int

    init(timeout: TimeInterval = 0.8, concurrency: Int = 16) {
        self.timeout = timeout
        self.concurrency = max(1, concurrency)
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        await ReversePTRSocketDiscovery(
            multicastAddress: "224.0.0.251",
            port: 5353,
            timeout: timeout,
            concurrency: concurrency,
            transactionID: 0
        )
        .discoverMetadata(for: ipAddresses)
    }

    static func hostname(from response: Data, ipAddress: String) -> String? {
        DNSPTRPacketParser.hostname(from: response, ipAddress: ipAddress)
    }
}

struct LLMNRReverseMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval
    private let concurrency: Int

    init(timeout: TimeInterval = 0.7, concurrency: Int = 16) {
        self.timeout = timeout
        self.concurrency = max(1, concurrency)
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        await ReversePTRSocketDiscovery(
            multicastAddress: "224.0.0.252",
            port: 5355,
            timeout: timeout,
            concurrency: concurrency,
            transactionID: 0x4c47
        )
        .discoverMetadata(for: ipAddresses)
    }

    static func hostname(from response: Data, ipAddress: String) -> String? {
        DNSPTRPacketParser.hostname(from: response, ipAddress: ipAddress)
    }
}

struct MDNSServiceMetadataDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval
    private let retryCount: Int
    private let retryDelay: TimeInterval
    private let serviceTypes: [String]

    init(
        timeout: TimeInterval = 1.8,
        retryCount: Int = 3,
        retryDelay: TimeInterval = 0.25,
        serviceTypes: [String] = [
            "_hap._tcp.local",
            "_services._dns-sd._udp.local",
            "_http._tcp.local",
            "_arduino._tcp.local",
            "_esphomelib._tcp.local",
            "_workstation._tcp.local",
            "_ssh._tcp.local",
        ]
    ) {
        self.timeout = timeout
        self.retryCount = max(1, retryCount)
        self.retryDelay = retryDelay
        self.serviceTypes = serviceTypes
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        let allowedIPs = Set(ipAddresses)
        guard !allowedIPs.isEmpty else { return [:] }

        let hostnamesByIP = await MDNSServiceSocketClient(
            timeout: timeout,
            retryCount: retryCount,
            retryDelay: retryDelay,
            serviceTypes: serviceTypes
        )
        .discoverHostnames()

        var metadataByIP: [String: DeviceMetadata] = [:]
        for (ipAddress, hostname) in hostnamesByIP where allowedIPs.contains(ipAddress) {
            metadataByIP[ipAddress] = DeviceMetadata(vendor: nil, hostname: hostname)
        }
        return metadataByIP
    }

    static func hostnamesByIP(from response: Data) -> [String: String] {
        DNSPTRPacketParser.hostnamesByIPv4Address(from: response)
    }

    static func serviceHostname(from response: Data) -> String? {
        DNSPTRPacketParser.serviceHostname(from: response)
    }
}

private struct MDNSServiceSocketClient: Sendable {
    let timeout: TimeInterval
    let retryCount: Int
    let retryDelay: TimeInterval
    let serviceTypes: [String]

    func discoverHostnames() async -> [String: String] {
        await Task.detached(priority: .utility) {
            var hostnamesByIP: [String: String] = [:]
            let socketFD = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
            guard socketFD >= 0 else { return hostnamesByIP }
            defer { close(socketFD) }

            guard configureMDNSReceiveSocket(socketFD) else {
                return hostnamesByIP
            }

            var receiveTimeout = timeval(
                tv_sec: Int(timeout),
                tv_usec: Int32((timeout.truncatingRemainder(dividingBy: 1)) * 1_000_000)
            )
            setsockopt(socketFD, SOL_SOCKET, SO_RCVTIMEO, &receiveTimeout, socklen_t(MemoryLayout<timeval>.size))

            var ttl: UInt8 = 255
            setsockopt(socketFD, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, socklen_t(MemoryLayout<UInt8>.size))

            var destination = sockaddr_in()
            destination.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            destination.sin_family = sa_family_t(AF_INET)
            destination.sin_port = UInt16(5353).bigEndian
            guard inet_pton(AF_INET, "224.0.0.251", &destination.sin_addr) == 1 else {
                return hostnamesByIP
            }

            for attempt in 0..<retryCount {
                for serviceType in serviceTypes {
                    let query = DNSPTRPacketParser.query(name: serviceType, transactionID: 0)
                    _ = withUnsafePointer(to: &destination) { pointer in
                        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                            query.withUnsafeBytes { bytes in
                                sendto(
                                    socketFD,
                                    bytes.baseAddress,
                                    query.count,
                                    0,
                                    sockaddrPointer,
                                    socklen_t(MemoryLayout<sockaddr_in>.size)
                                )
                            }
                        }
                    }
                }

                if attempt + 1 < retryCount {
                    usleep(useconds_t(max(0, retryDelay) * 1_000_000))
                }
            }

            while true {
                var buffer = [UInt8](repeating: 0, count: 9000)
                var source = sockaddr_storage()
                var sourceLength = socklen_t(MemoryLayout<sockaddr_storage>.size)
                let count = withUnsafeMutablePointer(to: &source) { pointer in
                    pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                        recvfrom(socketFD, &buffer, buffer.count, 0, sockaddrPointer, &sourceLength)
                    }
                }
                guard count > 0 else { break }

                let response = Data(buffer.prefix(count))
                for (ipAddress, hostname) in DNSPTRPacketParser.hostnamesByIPv4Address(
                    from: response
                ) {
                    hostnamesByIP[ipAddress] = hostname
                }

                if let sourceIP = ipAddress(from: source),
                   hostnamesByIP[sourceIP] == nil,
                   let hostname = DNSPTRPacketParser.serviceHostname(from: response) {
                    hostnamesByIP[sourceIP] = hostname
                }
            }

            return hostnamesByIP
        }.value
    }

    private func ipAddress(from source: sockaddr_storage) -> String? {
        guard Int32(source.ss_family) == AF_INET else { return nil }
        var source = source
        var addressBuffer = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))

        return withUnsafePointer(to: &source) { pointer in
            pointer.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { sockaddrPointer in
                var address = sockaddrPointer.pointee.sin_addr
                guard inet_ntop(AF_INET, &address, &addressBuffer, socklen_t(INET_ADDRSTRLEN)) != nil else {
                    return nil
                }
                let characters = addressBuffer.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }
                return String(decoding: characters, as: UTF8.self)
            }
        }
    }
}

private struct ReversePTRSocketDiscovery: NetworkMetadataDiscovering {
    let multicastAddress: String
    let port: UInt16
    let timeout: TimeInterval
    let concurrency: Int
    let transactionID: UInt16

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        var metadataByIP: [String: DeviceMetadata] = [:]
        let uniqueIPs = Array(Set(ipAddresses)).sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

        for batchStart in stride(from: uniqueIPs.startIndex, to: uniqueIPs.endIndex, by: concurrency) {
            let batchEnd = min(batchStart + concurrency, uniqueIPs.endIndex)
            let batch = Array(uniqueIPs[batchStart..<batchEnd])

            await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
                for ipAddress in batch {
                    group.addTask {
                        guard let hostname = await resolveHostname(ipAddress: ipAddress) else {
                            return nil
                        }
                        return (ipAddress, DeviceMetadata(vendor: nil, hostname: hostname))
                    }
                }

                for await result in group {
                    guard let (ipAddress, metadata) = result else { continue }
                    metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
                }
            }
        }

        return metadataByIP
    }

    private func resolveHostname(ipAddress: String) async -> String? {
        guard let queryName = reversePTRQuery(for: ipAddress) else { return nil }

        return await Task.detached(priority: .utility) {
            let socketFD = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
            guard socketFD >= 0 else { return nil }
            defer { close(socketFD) }

            if multicastAddress == "224.0.0.251", port == 5353, !configureMDNSReceiveSocket(socketFD) {
                return nil
            }

            var receiveTimeout = timeval(
                tv_sec: Int(timeout),
                tv_usec: Int32((timeout.truncatingRemainder(dividingBy: 1)) * 1_000_000)
            )
            setsockopt(socketFD, SOL_SOCKET, SO_RCVTIMEO, &receiveTimeout, socklen_t(MemoryLayout<timeval>.size))

            var ttl: UInt8 = 255
            setsockopt(socketFD, IPPROTO_IP, IP_MULTICAST_TTL, &ttl, socklen_t(MemoryLayout<UInt8>.size))

            var destination = sockaddr_in()
            destination.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            destination.sin_family = sa_family_t(AF_INET)
            destination.sin_port = port.bigEndian
            guard inet_pton(AF_INET, multicastAddress, &destination.sin_addr) == 1 else {
                return nil
            }

            let query = DNSPTRPacketParser.query(name: queryName, transactionID: transactionID)
            _ = withUnsafePointer(to: &destination) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    query.withUnsafeBytes { bytes in
                        sendto(
                            socketFD,
                            bytes.baseAddress,
                            query.count,
                            0,
                            sockaddrPointer,
                            socklen_t(MemoryLayout<sockaddr_in>.size)
                        )
                    }
                }
            }

            var buffer = [UInt8](repeating: 0, count: 1500)
            let count = recvfrom(socketFD, &buffer, buffer.count, 0, nil, nil)
            guard count > 0 else { return nil }

            return DNSPTRPacketParser.hostname(
                from: Data(buffer.prefix(count)),
                ipAddress: ipAddress
            )
        }.value
    }

    private func reversePTRQuery(for ipAddress: String) -> String? {
        let parts = ipAddress.split(separator: ".")
        guard parts.count == 4, parts.allSatisfy({ UInt8($0) != nil }) else {
            return nil
        }
        return parts.reversed().joined(separator: ".") + ".in-addr.arpa"
    }
}

struct NetBIOSNameDiscovery: NetworkMetadataDiscovering {
    private let timeout: TimeInterval
    private let concurrency: Int

    init(timeout: TimeInterval = 0.7, concurrency: Int = 16) {
        self.timeout = timeout
        self.concurrency = max(1, concurrency)
    }

    func discoverMetadata(for ipAddresses: [String]) async -> [String: DeviceMetadata] {
        var metadataByIP: [String: DeviceMetadata] = [:]
        let uniqueIPs = Array(Set(ipAddresses)).sorted { IPAddressSortKey($0) < IPAddressSortKey($1) }

        for batchStart in stride(from: uniqueIPs.startIndex, to: uniqueIPs.endIndex, by: concurrency) {
            let batchEnd = min(batchStart + concurrency, uniqueIPs.endIndex)
            let batch = Array(uniqueIPs[batchStart..<batchEnd])

            await withTaskGroup(of: (String, DeviceMetadata)?.self) { group in
                for ipAddress in batch {
                    group.addTask {
                        guard let hostname = await resolveHostname(ipAddress: ipAddress, timeout: timeout) else {
                            return nil
                        }
                        return (ipAddress, DeviceMetadata(vendor: nil, hostname: hostname))
                    }
                }

                for await result in group {
                    guard let (ipAddress, metadata) = result else { continue }
                    metadataByIP[ipAddress] = metadataByIP[ipAddress]?.merged(with: metadata) ?? metadata
                }
            }
        }

        return metadataByIP
    }

    static func hostname(fromNodeStatusResponse data: Data, ipAddress: String) -> String? {
        let bytes = Array(data)
        guard bytes.count > 57 else { return nil }

        for offset in 12..<(bytes.count - 4) {
            let nameCount = Int(bytes[offset])
            guard nameCount > 0, nameCount <= 32 else { continue }

            let namesStart = offset + 1
            let namesEnd = namesStart + nameCount * 18
            guard namesEnd <= bytes.count else { continue }

            var workstationName: String?
            var firstUniqueName: String?

            for nameOffset in stride(from: namesStart, to: namesEnd, by: 18) {
                let rawNameBytes = bytes[nameOffset..<(nameOffset + 15)]
                let suffix = bytes[nameOffset + 15]
                let flags = UInt16(bytes[nameOffset + 16]) << 8 | UInt16(bytes[nameOffset + 17])
                let isGroup = flags & 0x8000 != 0
                let rawName = String(decoding: rawNameBytes, as: UTF8.self)
                    .trimmingCharacters(in: .whitespacesAndNewlines)

                guard !isGroup,
                      !rawName.isEmpty,
                      !rawName.hasPrefix("__"),
                      let cleaned = HostnameResolver.clean(rawName, ipAddress: ipAddress) else {
                    continue
                }

                if suffix == 0x00 {
                    workstationName = cleaned
                    break
                }

                if firstUniqueName == nil {
                    firstUniqueName = cleaned
                }
            }

            return workstationName ?? firstUniqueName
        }

        return nil
    }

    private func resolveHostname(ipAddress: String, timeout: TimeInterval) async -> String? {
        await Task.detached(priority: .utility) {
            let socketFD = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
            guard socketFD >= 0 else { return nil }
            defer { close(socketFD) }

            var receiveTimeout = timeval(
                tv_sec: Int(timeout),
                tv_usec: Int32((timeout.truncatingRemainder(dividingBy: 1)) * 1_000_000)
            )
            setsockopt(socketFD, SOL_SOCKET, SO_RCVTIMEO, &receiveTimeout, socklen_t(MemoryLayout<timeval>.size))

            var destination = sockaddr_in()
            destination.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            destination.sin_family = sa_family_t(AF_INET)
            destination.sin_port = UInt16(137).bigEndian
            guard inet_pton(AF_INET, ipAddress, &destination.sin_addr) == 1 else {
                return nil
            }

            let query = nodeStatusQuery()
            _ = withUnsafePointer(to: &destination) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    query.withUnsafeBytes { bytes in
                        sendto(
                            socketFD,
                            bytes.baseAddress,
                            query.count,
                            0,
                            sockaddrPointer,
                            socklen_t(MemoryLayout<sockaddr_in>.size)
                        )
                    }
                }
            }

            var buffer = [UInt8](repeating: 0, count: 1024)
            let count = recvfrom(socketFD, &buffer, buffer.count, 0, nil, nil)
            guard count > 0 else { return nil }

            return Self.hostname(
                fromNodeStatusResponse: Data(buffer.prefix(count)),
                ipAddress: ipAddress
            )
        }.value
    }

    private func nodeStatusQuery() -> Data {
        var data = Data()
        data.append(contentsOf: [0x4c, 0x47, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        data.append(0x20)

        let wildcard = Array("*".utf8) + Array(repeating: UInt8(ascii: " "), count: 15)
        for byte in wildcard.prefix(16) {
            data.append(UInt8(ascii: "A") + ((byte >> 4) & 0x0f))
            data.append(UInt8(ascii: "A") + (byte & 0x0f))
        }

        data.append(0x00)
        data.append(contentsOf: [0x00, 0x21, 0x00, 0x01])
        return data
    }
}

struct SSDPResponse: Equatable, Sendable {
    var ipAddress: String
    var headers: [String: String]

    static func parse(_ response: String, ipAddress: String) -> SSDPResponse {
        var headers: [String: String] = [:]
        for line in response.components(separatedBy: .newlines).dropFirst() {
            guard let separator = line.firstIndex(of: ":") else { continue }
            let key = line[..<separator].trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let value = line[line.index(after: separator)...].trimmingCharacters(in: .whitespacesAndNewlines)
            if !key.isEmpty, !value.isEmpty {
                headers[key] = value
            }
        }
        return SSDPResponse(ipAddress: ipAddress, headers: headers)
    }
}

private struct SSDPSocketClient: Sendable {
    let timeout: TimeInterval

    func discover() async -> [SSDPResponse] {
        await Task.detached(priority: .utility) {
            var responses: [SSDPResponse] = []
            let socketFD = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP)
            guard socketFD >= 0 else { return responses }
            defer { close(socketFD) }

            var receiveTimeout = timeval(
                tv_sec: Int(timeout),
                tv_usec: Int32((timeout.truncatingRemainder(dividingBy: 1)) * 1_000_000)
            )
            setsockopt(socketFD, SOL_SOCKET, SO_RCVTIMEO, &receiveTimeout, socklen_t(MemoryLayout<timeval>.size))

            let request = """
            M-SEARCH * HTTP/1.1\r
            HOST: 239.255.255.250:1900\r
            MAN: "ssdp:discover"\r
            MX: 1\r
            ST: ssdp:all\r
            \r
            """
            let requestBytes = Array(request.utf8)

            var destination = sockaddr_in()
            destination.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
            destination.sin_family = sa_family_t(AF_INET)
            destination.sin_port = UInt16(1900).bigEndian
            inet_pton(AF_INET, "239.255.255.250", &destination.sin_addr)

            _ = withUnsafePointer(to: &destination) { pointer in
                pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                    requestBytes.withUnsafeBytes { bytes in
                        sendto(
                            socketFD,
                            bytes.baseAddress,
                            requestBytes.count,
                            0,
                            sockaddrPointer,
                            socklen_t(MemoryLayout<sockaddr_in>.size)
                        )
                    }
                }
            }

            var seenIPs = Set<String>()
            while true {
                var buffer = [UInt8](repeating: 0, count: 8192)
                var source = sockaddr_storage()
                var sourceLength = socklen_t(MemoryLayout<sockaddr_storage>.size)

                let count = withUnsafeMutablePointer(to: &source) { pointer in
                    pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
                        recvfrom(socketFD, &buffer, buffer.count, 0, sockaddrPointer, &sourceLength)
                    }
                }

                guard count > 0 else { break }
                guard let ipAddress = ipAddress(from: source), !seenIPs.contains(ipAddress) else { continue }
                seenIPs.insert(ipAddress)

                let response = String(decoding: buffer.prefix(count), as: UTF8.self)
                responses.append(SSDPResponse.parse(response, ipAddress: ipAddress))
            }

            return responses
        }.value
    }

    private func ipAddress(from source: sockaddr_storage) -> String? {
        guard Int32(source.ss_family) == AF_INET else { return nil }
        var source = source
        var addressBuffer = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))

        return withUnsafePointer(to: &source) { pointer in
            pointer.withMemoryRebound(to: sockaddr_in.self, capacity: 1) { sockaddrPointer in
                var address = sockaddrPointer.pointee.sin_addr
                guard inet_ntop(AF_INET, &address, &addressBuffer, socklen_t(INET_ADDRSTRLEN)) != nil else {
                    return nil
                }
                let characters = addressBuffer.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }
                return String(decoding: characters, as: UTF8.self)
            }
        }
    }
}

enum DNSPTRPacketParser {
    static func query(name: String, transactionID: UInt16) -> Data {
        var data = Data()
        appendUInt16(transactionID, to: &data)
        appendUInt16(0x0000, to: &data)
        appendUInt16(0x0001, to: &data)
        appendUInt16(0x0000, to: &data)
        appendUInt16(0x0000, to: &data)
        appendUInt16(0x0000, to: &data)

        for label in name.split(separator: ".") {
            let bytes = Array(label.utf8.prefix(63))
            data.append(UInt8(bytes.count))
            data.append(contentsOf: bytes)
        }
        data.append(0x00)
        appendUInt16(0x000c, to: &data)
        appendUInt16(0x0001, to: &data)
        return data
    }

    static func hostname(from response: Data, ipAddress: String) -> String? {
        let bytes = Array(response)
        guard bytes.count >= 12 else { return nil }

        let questionCount = Int(readUInt16(bytes, at: 4) ?? 0)
        let answerCount = Int(readUInt16(bytes, at: 6) ?? 0)
        guard answerCount > 0 else { return nil }

        var offset = 12
        for _ in 0..<questionCount {
            guard skipName(bytes, offset: &offset),
                  offset + 4 <= bytes.count else {
                return nil
            }
            offset += 4
        }

        let expectedOwner = reversePTRName(for: ipAddress)
        for _ in 0..<answerCount {
            guard let recordName = readName(bytes, offset: offset) else {
                return nil
            }
            offset = recordName.nextOffset
            guard let recordType = readUInt16(bytes, at: offset),
                  offset + 10 <= bytes.count else {
                return nil
            }

            offset += 2
            _ = readUInt16(bytes, at: offset)
            offset += 2
            offset += 4
            guard let recordLength = readUInt16(bytes, at: offset) else { return nil }
            offset += 2

            let dataOffset = offset
            let dataEnd = dataOffset + Int(recordLength)
            guard dataEnd <= bytes.count else { return nil }

            if recordType == 0x000c,
               normalizedDNSName(recordName.name) == expectedOwner,
               let candidate = readName(bytes, offset: dataOffset)?.name,
               let hostname = HostnameResolver.clean(candidate, ipAddress: ipAddress) {
                return hostname
            }

            offset = dataEnd
        }

        return nil
    }

    private static func reversePTRName(for ipAddress: String) -> String? {
        let parts = ipAddress.split(separator: ".")
        guard parts.count == 4, parts.allSatisfy({ UInt8($0) != nil }) else {
            return nil
        }
        return parts.reversed().joined(separator: ".") + ".in-addr.arpa"
    }

    private static func normalizedDNSName(_ value: String) -> String {
        value.trimmingCharacters(in: CharacterSet(charactersIn: ".")).lowercased()
    }

    static func hostnamesByIPv4Address(from response: Data) -> [String: String] {
        let bytes = Array(response)
        guard bytes.count >= 12 else { return [:] }

        let questionCount = Int(readUInt16(bytes, at: 4) ?? 0)
        let answerCount = Int(readUInt16(bytes, at: 6) ?? 0)
        let authorityCount = Int(readUInt16(bytes, at: 8) ?? 0)
        let additionalCount = Int(readUInt16(bytes, at: 10) ?? 0)
        let recordCount = answerCount + authorityCount + additionalCount
        guard recordCount > 0 else { return [:] }

        var offset = 12
        for _ in 0..<questionCount {
            guard skipName(bytes, offset: &offset),
                  offset + 4 <= bytes.count else {
                return [:]
            }
            offset += 4
        }

        var addressRecords: [(host: String, ipAddress: String)] = []
        var serviceNamesByTarget: [String: String] = [:]
        for _ in 0..<recordCount {
            guard let recordName = readName(bytes, offset: offset) else {
                return buildHostnamesByIP(
                    addressRecords: addressRecords,
                    serviceNamesByTarget: serviceNamesByTarget
                )
            }
            offset = recordName.nextOffset
            guard let recordType = readUInt16(bytes, at: offset),
                  offset + 10 <= bytes.count else {
                return buildHostnamesByIP(
                    addressRecords: addressRecords,
                    serviceNamesByTarget: serviceNamesByTarget
                )
            }

            offset += 2
            _ = readUInt16(bytes, at: offset)
            offset += 2
            offset += 4
            guard let recordLength = readUInt16(bytes, at: offset) else {
                return buildHostnamesByIP(
                    addressRecords: addressRecords,
                    serviceNamesByTarget: serviceNamesByTarget
                )
            }
            offset += 2

            let dataOffset = offset
            let dataEnd = dataOffset + Int(recordLength)
            guard dataEnd <= bytes.count else {
                return buildHostnamesByIP(
                    addressRecords: addressRecords,
                    serviceNamesByTarget: serviceNamesByTarget
                )
            }

            if recordType == 0x0001, recordLength == 4 {
                let ipAddress = "\(bytes[dataOffset]).\(bytes[dataOffset + 1]).\(bytes[dataOffset + 2]).\(bytes[dataOffset + 3])"
                addressRecords.append((host: recordName.name, ipAddress: ipAddress))
            } else if recordType == 0x0021,
                      let target = srvTargetName(bytes, offset: dataOffset, length: Int(recordLength)),
                      let serviceHostname = serviceInstanceHostname(from: recordName.name) {
                serviceNamesByTarget[target.lowercased()] = serviceHostname
            }

            offset = dataEnd
        }

        return buildHostnamesByIP(
            addressRecords: addressRecords,
            serviceNamesByTarget: serviceNamesByTarget
        )
    }

    static func serviceHostname(from response: Data) -> String? {
        let bytes = Array(response)
        guard bytes.count >= 12 else { return nil }

        let questionCount = Int(readUInt16(bytes, at: 4) ?? 0)
        let answerCount = Int(readUInt16(bytes, at: 6) ?? 0)
        let authorityCount = Int(readUInt16(bytes, at: 8) ?? 0)
        let additionalCount = Int(readUInt16(bytes, at: 10) ?? 0)
        let recordCount = answerCount + authorityCount + additionalCount
        guard recordCount > 0 else { return nil }

        var offset = 12
        for _ in 0..<questionCount {
            guard skipName(bytes, offset: &offset),
                  offset + 4 <= bytes.count else {
                return nil
            }
            offset += 4
        }

        for _ in 0..<recordCount {
            guard let recordName = readName(bytes, offset: offset) else { return nil }
            offset = recordName.nextOffset
            guard let recordType = readUInt16(bytes, at: offset),
                  offset + 10 <= bytes.count else {
                return nil
            }

            offset += 2
            _ = readUInt16(bytes, at: offset)
            offset += 2
            offset += 4
            guard let recordLength = readUInt16(bytes, at: offset) else { return nil }
            offset += 2

            let dataOffset = offset
            let dataEnd = dataOffset + Int(recordLength)
            guard dataEnd <= bytes.count else { return nil }

            if recordType == 0x0021,
               let hostname = serviceInstanceHostname(from: recordName.name) {
                return hostname
            }

            if recordType == 0x000c,
               let serviceName = readName(bytes, offset: dataOffset)?.name,
               let hostname = serviceInstanceHostname(from: serviceName) {
                return hostname
            }

            offset = dataEnd
        }

        return nil
    }

    private static func appendUInt16(_ value: UInt16, to data: inout Data) {
        data.append(UInt8((value >> 8) & 0xff))
        data.append(UInt8(value & 0xff))
    }

    private static func readUInt16(_ bytes: [UInt8], at offset: Int) -> UInt16? {
        guard offset + 1 < bytes.count else { return nil }
        return UInt16(bytes[offset]) << 8 | UInt16(bytes[offset + 1])
    }

    private static func srvTargetName(_ bytes: [UInt8], offset: Int, length: Int) -> String? {
        guard length >= 7 else { return nil }
        return readName(bytes, offset: offset + 6)?.name
    }

    private static func serviceInstanceHostname(from name: String) -> String? {
        let lowered = name.lowercased()
        let serviceSuffixes = [
            "._hap._tcp.local",
            "._http._tcp.local",
            "._arduino._tcp.local",
            "._esphomelib._tcp.local",
            "._workstation._tcp.local",
            "._ssh._tcp.local",
        ]

        for suffix in serviceSuffixes where lowered.hasSuffix(suffix) {
            let instanceName = String(name.dropLast(suffix.count))
            return HostnameResolver.clean(instanceName)
        }

        return nil
    }

    private static func buildHostnamesByIP(
        addressRecords: [(host: String, ipAddress: String)],
        serviceNamesByTarget: [String: String]
    ) -> [String: String] {
        var hostnamesByIP: [String: String] = [:]
        for addressRecord in addressRecords {
            let serviceName = serviceNamesByTarget[addressRecord.host.lowercased()]
            if let hostname = HostnameResolver.clean(serviceName ?? addressRecord.host, ipAddress: addressRecord.ipAddress) {
                hostnamesByIP[addressRecord.ipAddress] = hostname
            }
        }
        return hostnamesByIP
    }

    private static func skipName(_ bytes: [UInt8], offset: inout Int) -> Bool {
        guard let result = readName(bytes, offset: offset) else { return false }
        offset = result.nextOffset
        return true
    }

    private static func readName(_ bytes: [UInt8], offset: Int) -> (name: String, nextOffset: Int)? {
        var labels: [String] = []
        var cursor = offset
        var nextOffset: Int?
        var jumps = 0

        while cursor < bytes.count {
            let length = bytes[cursor]

            if length == 0 {
                cursor += 1
                return (labels.joined(separator: "."), nextOffset ?? cursor)
            }

            if length & 0xc0 == 0xc0 {
                guard cursor + 1 < bytes.count else { return nil }
                let pointer = (Int(length & 0x3f) << 8) | Int(bytes[cursor + 1])
                guard pointer < bytes.count, jumps < 8 else { return nil }
                nextOffset = nextOffset ?? cursor + 2
                cursor = pointer
                jumps += 1
                continue
            }

            guard length & 0xc0 == 0,
                  cursor + 1 + Int(length) <= bytes.count else {
                return nil
            }

            let start = cursor + 1
            let end = start + Int(length)
            labels.append(String(decoding: bytes[start..<end], as: UTF8.self))
            cursor = end
        }

        return nil
    }
}

private func configureMDNSReceiveSocket(_ socketFD: Int32) -> Bool {
    var reuse: Int32 = 1
    setsockopt(socketFD, SOL_SOCKET, SO_REUSEADDR, &reuse, socklen_t(MemoryLayout<Int32>.size))
    setsockopt(socketFD, SOL_SOCKET, SO_REUSEPORT, &reuse, socklen_t(MemoryLayout<Int32>.size))

    var address = sockaddr_in()
    address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    address.sin_family = sa_family_t(AF_INET)
    address.sin_port = UInt16(5353).bigEndian
    address.sin_addr = in_addr(s_addr: INADDR_ANY)

    let bindResult = withUnsafePointer(to: &address) { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPointer in
            bind(socketFD, sockaddrPointer, socklen_t(MemoryLayout<sockaddr_in>.size))
        }
    }
    guard bindResult == 0 else { return false }

    var membership = ip_mreq()
    guard inet_pton(AF_INET, "224.0.0.251", &membership.imr_multiaddr) == 1 else {
        return false
    }
    membership.imr_interface = in_addr(s_addr: INADDR_ANY)

    let joinResult = setsockopt(
        socketFD,
        IPPROTO_IP,
        IP_ADD_MEMBERSHIP,
        &membership,
        socklen_t(MemoryLayout<ip_mreq>.size)
    )
    return joinResult == 0
}

private extension DeviceMetadata {
    func merged(with other: DeviceMetadata) -> DeviceMetadata {
        DeviceMetadata(
            vendor: other.vendor ?? vendor,
            hostname: other.hostname ?? hostname
        )
    }
}
