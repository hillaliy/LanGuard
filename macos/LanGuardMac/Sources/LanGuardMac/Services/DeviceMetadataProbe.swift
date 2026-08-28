import Foundation

struct DeviceMetadata: Equatable, Sendable {
    var vendor: String?
    var vendorSource: DeviceIdentitySource?
    var hostname: String?
    var hostnameSource: DeviceIdentitySource?

    init(
        vendor: String? = nil,
        vendorSource: DeviceIdentitySource? = nil,
        hostname: String? = nil,
        hostnameSource: DeviceIdentitySource? = nil
    ) {
        self.vendor = vendor
        self.vendorSource = vendor == nil ? nil : vendorSource
        self.hostname = HostnameResolver.clean(hostname)
        self.hostnameSource = self.hostname == nil ? nil : hostnameSource
    }
}

protocol DeviceMetadataProbing: Sendable {
    func probe(host: String, openPorts: [Int]) async -> DeviceMetadata
}

struct HTTPDeviceMetadataProbe: DeviceMetadataProbing {
    private let timeout: TimeInterval
    private let maxBodyBytes: Int

    init(timeout: TimeInterval = 1.5, maxBodyBytes: Int = 64_000) {
        self.timeout = timeout
        self.maxBodyBytes = maxBodyBytes
    }

    func probe(host: String, openPorts: [Int]) async -> DeviceMetadata {
        for requestURL in candidateURLs(host: host, openPorts: openPorts) {
            guard let metadata = await metadata(from: requestURL), metadata.vendor != nil || metadata.hostname != nil else {
                continue
            }
            return metadata
        }

        return DeviceMetadata()
    }

    private func candidateURLs(host: String, openPorts: [Int]) -> [URL] {
        let httpPorts = [80, 8080, 8000, 8081]
        let httpsPorts = [443, 8443]
        let ports = Set(openPorts)
        var urls: [URL] = []

        for port in httpPorts where ports.contains(port) {
            if let url = URL(string: "http://\(host):\(port)/") {
                urls.append(url)
            }
        }

        for port in httpsPorts where ports.contains(port) {
            if let url = URL(string: "https://\(host):\(port)/") {
                urls.append(url)
            }
        }

        return urls
    }

    private func metadata(from url: URL) async -> DeviceMetadata? {
        var request = URLRequest(url: url)
        request.timeoutInterval = timeout
        request.setValue("LanGuard/1.0", forHTTPHeaderField: "User-Agent")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else { return nil }

            let body = String(data: data.prefix(maxBodyBytes), encoding: .utf8) ?? ""
            return Self.metadata(headers: httpResponse.allHeaderFields, body: body)
        } catch {
            return nil
        }
    }

    static func metadata(headers: [AnyHashable: Any], body: String) -> DeviceMetadata {
        let vendorHeaders = [
            "manufacturer",
            "x-manufacturer",
            "x-device-manufacturer",
            "x-vendor",
            "x-device-vendor",
            "x-brand",
        ]
        let headerVendor = headers.first { key, _ in
            vendorHeaders.contains(String(describing: key).lowercased())
        }.map { _, value in String(describing: value) }

        let metaVendor = firstMetaContent(in: body, names: ["manufacturer", "vendor", "brand", "application-name"])
        let jsonVendor = firstMatch(in: body, pattern: #""(?:manufacturer|vendor|brand)"\s*:\s*"([^"]+)""#)
        let xmlVendor = firstMatch(in: body, pattern: #"<(?:manufacturer|vendor|brand)>\s*([^<]+)\s*</(?:manufacturer|vendor|brand)>"#)
        let vendor = MACVendorResolver.displayVendor(headerVendor ?? metaVendor ?? jsonVendor ?? xmlVendor)
        let hostnameHeaders = [
            "hostname",
            "x-hostname",
            "x-device-name",
            "x-friendly-name",
            "device-name",
            "friendly-name",
        ]
        let headerHostname = headers.first { key, _ in
            hostnameHeaders.contains(String(describing: key).lowercased())
        }.map { _, value in String(describing: value) }
        let metaHostname = firstMetaContent(in: body, names: ["hostname", "device-name", "friendly-name"])
        let jsonHostname = firstMatch(in: body, pattern: #""(?:hostname|deviceName|device_name|friendlyName|friendly_name|name)"\s*:\s*"([^"]+)""#)
        let xmlHostname = firstMatch(in: body, pattern: #"<(?:hostname|deviceName|device_name|friendlyName|friendly_name|name)>\s*([^<]+)\s*</(?:hostname|deviceName|device_name|friendlyName|friendly_name|name)>"#)
        let titleHostname = firstHTMLTitle(in: body)
        let hostname = firstUsableHostname([headerHostname, metaHostname, jsonHostname, xmlHostname, titleHostname])

        return DeviceMetadata(
            vendor: vendor,
            vendorSource: vendor == nil ? nil : .http,
            hostname: hostname,
            hostnameSource: hostname == nil ? nil : .http
        )
    }

    private static func firstMetaContent(in body: String, names: [String]) -> String? {
        for name in names {
            let escapedName = NSRegularExpression.escapedPattern(for: name)
            if let value = firstMatch(
                in: body,
                pattern: #"<meta[^>]+name=["']\#(escapedName)["'][^>]+content=["']([^"']+)["']"#
            ) {
                return value
            }
            if let value = firstMatch(
                in: body,
                pattern: #"<meta[^>]+content=["']([^"']+)["'][^>]+name=["']\#(escapedName)["']"#
            ) {
                return value
            }
        }
        return nil
    }

    private static func firstHTMLTitle(in body: String) -> String? {
        firstMatch(in: body, pattern: #"<title[^>]*>\s*([^<]+)\s*</title>"#)
    }

    private static func firstUsableHostname(_ candidates: [String?]) -> String? {
        for candidate in candidates {
            guard let cleaned = HostnameResolver.clean(candidate) else { continue }
            let lowered = cleaned.lowercased()
            guard !genericHostnames.contains(lowered) else { continue }
            return cleaned
        }
        return nil
    }

    private static let genericHostnames: Set<String> = [
        "admin",
        "camera",
        "device",
        "home",
        "index",
        "ip camera",
        "login",
        "router",
        "setup",
        "web server",
        "webcam",
        "welcome",
    ]

    private static func firstMatch(in text: String, pattern: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive, .dotMatchesLineSeparators]) else {
            return nil
        }
        let range = NSRange(text.startIndex..<text.endIndex, in: text)
        guard
            let match = regex.firstMatch(in: text, range: range),
            match.numberOfRanges > 1,
            let matchRange = Range(match.range(at: 1), in: text)
        else {
            return nil
        }
        return String(text[matchRange])
    }
}
